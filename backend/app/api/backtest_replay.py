from __future__ import annotations

from datetime import timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.strategies import ensure_default_strategies
from app.db.models import BacktestJob, ReplaySession, Strategy, StrategyVersion, utcnow
from app.db.session import get_db
from app.services.market_data import TIMEFRAME_SECONDS, sync_and_get_candles
from app.services.mexc_provider import get_mexc_client
from engine.backtest.runner import (
    run_event_driven_backtest,
    run_vectorized_backtest,
    run_walk_forward_optimization,
)
from engine.replay.controller import apply_replay_order, build_replay_view
from exchanges.mexc.market_client import MexcApiError, MexcMarketDataClient

bt_replay_router = APIRouter(prefix="/api/v1")


def _iso(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


class BacktestRunRequest(BaseModel):
    strategy_version_id: str
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="15m", min_length=2, max_length=16)
    bars: int = Field(default=300, ge=60, le=1500)
    initial_capital_usdt: float = Field(default=10000.0, ge=50.0, le=10_000_000.0)
    position_size_pct: float = Field(default=95.0, ge=5.0, le=100.0)
    fee_pct: float = Field(default=0.1, ge=0.0, le=2.0)
    slippage_pct: float = Field(default=0.05, ge=0.0, le=2.0)


class ReplayStartRequest(BaseModel):
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="15m", min_length=2, max_length=16)
    bars: int = Field(default=160, ge=60, le=500)
    start_cursor: int = Field(default=40, ge=10, le=450)
    initial_cash_usdt: float = Field(default=10000.0, ge=50.0)


class ReplayStepRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=50)


class ReplayOrderRequest(BaseModel):
    side: str
    qty: float = Field(gt=0.0)


@bt_replay_router.post("/backtests/run", status_code=status.HTTP_201_CREATED)
def run_backtest_endpoint(
    payload: BacktestRunRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    ensure_default_strategies(db)
    ver = db.execute(
        select(StrategyVersion).where(StrategyVersion.id == payload.strategy_version_id)
    ).scalar_one_or_none()
    if ver is None:
        raise HTTPException(status_code=404, detail="Strategy version not found")
    if payload.timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")

    try:
        synced = sync_and_get_candles(
            db, client, symbol=payload.symbol, timeframe=payload.timeframe, limit=payload.bars
        )
    except MexcApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    cfg = {
        "initial_capital_usdt": payload.initial_capital_usdt,
        "position_size_pct": payload.position_size_pct,
        "fee_pct": payload.fee_pct,
        "slippage_pct": payload.slippage_pct,
    }
    ev_res = run_event_driven_backtest(ver.definition_json, synced["items"], cfg)
    vec_res = run_vectorized_backtest(ver.definition_json, synced["items"], cfg)

    signals_match = (
        ev_res["entry_signals"] == vec_res["entry_signals"]
        and ev_res["exit_signals"] == vec_res["exit_signals"]
    )

    metrics_payload = {
        **ev_res["metrics"],
        "vectorized_approx_return_pct": vec_res["approx_return_pct"],
        "signal_parity": signals_match,
        "equity_curve": ev_res["equity_curve"],
        "drawdown_curve": ev_res["drawdown_curve"],
    }

    job = BacktestJob(
        strategy_version_id=ver.id,
        symbol=synced["symbol"],
        timeframe=synced["timeframe"],
        config_json=cfg,
        data_snapshot_hash=synced["quality"]["data_snapshot_hash"],
        status="completed",
        metrics_json=metrics_payload,
        trades_json=ev_res["trades"],
    )
    db.add(job)
    db.commit()

    return {
        "id": job.id,
        "strategy_version_id": ver.id,
        "symbol": job.symbol,
        "timeframe": job.timeframe,
        "data_snapshot_hash": job.data_snapshot_hash,
        "quality": synced["quality"],
        "metrics": ev_res["metrics"],
        "vectorized_parity": signals_match,
        "vectorized_approx_return_pct": vec_res["approx_return_pct"],
        "equity_curve": ev_res["equity_curve"],
        "drawdown_curve": ev_res["drawdown_curve"],
        "trades": ev_res["trades"],
        "created_at": _iso(job.created_at),
    }


@bt_replay_router.get("/backtests")
def list_backtest_jobs(db: Session = Depends(get_db)) -> dict[str, Any]:
    jobs = db.execute(select(BacktestJob).order_by(BacktestJob.created_at.desc()).limit(50)).scalars().all()
    versions = {v.id: v for v in db.execute(select(StrategyVersion)).scalars().all()}
    strategies = {s.id: s for s in db.execute(select(Strategy)).scalars().all()}

    items = []
    for j in jobs:
        v = versions.get(j.strategy_version_id)
        s = strategies.get(v.strategy_id) if v else None
        m = j.metrics_json or {}
        items.append(
            {
                "id": j.id,
                "strategy_version_id": j.strategy_version_id,
                "strategy_name": s.name if s else "Unknown",
                "version_no": v.version_no if v else 1,
                "symbol": j.symbol,
                "timeframe": j.timeframe,
                "data_snapshot_hash": j.data_snapshot_hash,
                "total_return_pct": m.get("total_return_pct", 0.0),
                "win_rate_pct": m.get("win_rate_pct", 0.0),
                "profit_factor": m.get("profit_factor", 0.0),
                "max_drawdown_pct": m.get("max_drawdown_pct", 0.0),
                "sharpe_ratio": m.get("sharpe_ratio", 0.0),
                "total_trades": m.get("total_trades", 0),
                "created_at": _iso(j.created_at),
            }
        )
    return {"items": items}


@bt_replay_router.get("/backtests/{job_id}")
def get_backtest_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.execute(select(BacktestJob).where(BacktestJob.id == job_id)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Backtest job not found")
    return {
        "id": job.id,
        "strategy_version_id": job.strategy_version_id,
        "symbol": job.symbol,
        "timeframe": job.timeframe,
        "config": job.config_json,
        "data_snapshot_hash": job.data_snapshot_hash,
        "metrics": job.metrics_json,
        "trades": job.trades_json,
        "created_at": _iso(job.created_at),
    }


@bt_replay_router.post("/backtests/optimize")
def optimize_backtest_endpoint(
    payload: BacktestRunRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    ver = db.execute(
        select(StrategyVersion).where(StrategyVersion.id == payload.strategy_version_id)
    ).scalar_one_or_none()
    if ver is None:
        raise HTTPException(status_code=404, detail="Strategy version not found")
    if payload.timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")

    try:
        synced = sync_and_get_candles(
            db, client, symbol=payload.symbol, timeframe=payload.timeframe, limit=payload.bars
        )
    except MexcApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    cfg = {
        "initial_capital_usdt": payload.initial_capital_usdt,
        "position_size_pct": payload.position_size_pct,
        "fee_pct": payload.fee_pct,
        "slippage_pct": payload.slippage_pct,
    }
    res = run_walk_forward_optimization(ver.definition_json, synced["items"], cfg)
    return {
        "strategy_version_id": ver.id,
        "symbol": synced["symbol"],
        "timeframe": synced["timeframe"],
        "data_snapshot_hash": synced["quality"]["data_snapshot_hash"],
        **res,
    }


@bt_replay_router.post("/replay/sessions", status_code=status.HTTP_201_CREATED)
def create_replay_session(
    payload: ReplayStartRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    if payload.timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")
    try:
        synced = sync_and_get_candles(
            db, client, symbol=payload.symbol, timeframe=payload.timeframe, limit=payload.bars
        )
    except MexcApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    candles = synced["items"]
    cursor = min(payload.start_cursor, max(0, len(candles) - 2))
    init_state = {
        "cash_usdt": payload.initial_cash_usdt,
        "position_qty": 0.0,
        "avg_entry_price": 0.0,
        "realized_pnl_usdt": 0.0,
        "trades": [],
    }
    sess = ReplaySession(
        symbol=synced["symbol"],
        timeframe=synced["timeframe"],
        candles_json=candles,
        cursor_index=cursor,
        total_bars=len(candles),
        state_json=init_state,
        status="active",
    )
    db.add(sess)
    db.commit()

    view = build_replay_view(candles, cursor, init_state)
    return {"id": sess.id, "symbol": sess.symbol, "timeframe": sess.timeframe, "status": sess.status, **view}


@bt_replay_router.get("/replay/sessions/{session_id}")
def get_replay_session(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    sess = db.execute(select(ReplaySession).where(ReplaySession.id == session_id)).scalar_one_or_none()
    if sess is None:
        raise HTTPException(status_code=404, detail="Replay session not found")
    view = build_replay_view(sess.candles_json, sess.cursor_index, sess.state_json)
    return {"id": sess.id, "symbol": sess.symbol, "timeframe": sess.timeframe, "status": sess.status, **view}


@bt_replay_router.post("/replay/sessions/{session_id}/step")
def step_replay_session(
    session_id: str,
    payload: ReplayStepRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sess = db.execute(select(ReplaySession).where(ReplaySession.id == session_id)).scalar_one_or_none()
    if sess is None:
        raise HTTPException(status_code=404, detail="Replay session not found")

    next_cursor = min(sess.total_bars - 1, sess.cursor_index + payload.steps)
    sess.cursor_index = next_cursor
    if next_cursor >= sess.total_bars - 1:
        sess.status = "completed"
    sess.updated_at = utcnow()
    db.commit()

    view = build_replay_view(sess.candles_json, sess.cursor_index, sess.state_json)
    return {"id": sess.id, "symbol": sess.symbol, "timeframe": sess.timeframe, "status": sess.status, **view}


@bt_replay_router.post("/replay/sessions/{session_id}/order")
def place_replay_order(
    session_id: str,
    payload: ReplayOrderRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sess = db.execute(select(ReplaySession).where(ReplaySession.id == session_id)).scalar_one_or_none()
    if sess is None:
        raise HTTPException(status_code=404, detail="Replay session not found")

    try:
        new_state = apply_replay_order(
            sess.candles_json, sess.cursor_index, sess.state_json, side=payload.side, qty=payload.qty
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sess.state_json = new_state
    sess.updated_at = utcnow()
    db.commit()

    view = build_replay_view(sess.candles_json, sess.cursor_index, sess.state_json)
    return {"id": sess.id, "symbol": sess.symbol, "timeframe": sess.timeframe, "status": sess.status, **view}
