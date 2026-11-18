from __future__ import annotations

from datetime import timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.router import get_optional_session_and_user
from app.db.models import Strategy, StrategyVersion, User, UserSession, utcnow
from app.db.session import get_db
from app.services.audit import append_audit_log
from app.services.market_data import TIMEFRAME_SECONDS, sync_and_get_candles
from app.services.mexc_provider import get_mexc_client
from engine.strategy.evaluator import (
    compute_definition_hash,
    evaluate_strategy,
    validate_strategy_definition,
)
from exchanges.mexc.market_client import MexcApiError, MexcMarketDataClient

strategies_router = APIRouter(prefix="/api/v1/strategies")

_VALID_STATUSES = {
    "Draft",
    "Validating",
    "Backtesting",
    "Paper Trading",
    "Approved",
    "Live",
    "Paused",
    "Disabled",
    "Archived",
}


def _iso(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def ensure_default_strategies(db: Session) -> None:
    """Seed two multi-indicator strategies (including 7-indicator BTC Momentum Pro) if empty."""
    if db.execute(select(Strategy.id).limit(1)).scalar_one_or_none() is not None:
        return

    defaults = [
        (
            "BTC Momentum & Volatility Pro",
            "Combines 7 indicators (EMA 20, EMA 50, SMA 200, RSI 14, MACD, Bollinger Bands, ATR 14) with conservative SL/TP.",
            "Approved",
            {
                "symbol": "BTC/USDT",
                "timeframe": "15m",
                "signal_mode": "closed_candle",
                "stop_loss_pct": 1.5,
                "take_profit_pct": 3.5,
                "indicators": [
                    {"key": "ema_fast", "indicator_id": "ema", "params": {"length": 20, "source": "close", "offset": 0}},
                    {"key": "ema_slow", "indicator_id": "ema", "params": {"length": 50, "source": "close", "offset": 0}},
                    {"key": "sma_trend", "indicator_id": "sma", "params": {"length": 200, "source": "close", "offset": 0}},
                    {"key": "rsi_main", "indicator_id": "rsi", "params": {"length": 14, "source": "close", "overbought": 70, "oversold": 30}},
                    {"key": "macd_main", "indicator_id": "macd", "params": {"fast_length": 12, "slow_length": 26, "signal_length": 9, "source": "close"}},
                    {"key": "bb_main", "indicator_id": "bb", "params": {"length": 20, "mult": 2.0, "source": "close"}},
                    {"key": "atr_main", "indicator_id": "atr", "params": {"length": 14}},
                ],
                "entry_rule": {
                    "type": "AND",
                    "children": [
                        {"type": "COMPARE", "left": "ema_fast.ema", "op": ">", "right": "ema_slow.ema"},
                        {"type": "COMPARE", "left": "rsi_main.rsi", "op": ">", "right": 48},
                        {"type": "COMPARE", "left": "macd_main.histogram", "op": ">", "right": 0},
                    ],
                },
                "exit_rule": {
                    "type": "OR",
                    "children": [
                        {"type": "CROSS_BELOW", "left": "ema_fast.ema", "right": "ema_slow.ema"},
                        {"type": "COMPARE", "left": "rsi_main.rsi", "op": ">", "right": 75},
                    ],
                },
            },
        ),
        (
            "ETH Mean Reversion & Trend Filter",
            "Combines 6 indicators (Bollinger Bands, RSI, Stochastic, EMA 50, ADX, VWAP) for range reversals.",
            "Backtesting",
            {
                "symbol": "ETH/USDT",
                "timeframe": "15m",
                "signal_mode": "closed_candle",
                "stop_loss_pct": 1.8,
                "take_profit_pct": 3.0,
                "indicators": [
                    {"key": "bb_main", "indicator_id": "bb", "params": {"length": 20, "mult": 2.0, "source": "close"}},
                    {"key": "rsi_main", "indicator_id": "rsi", "params": {"length": 14, "source": "close", "overbought": 70, "oversold": 30}},
                    {"key": "stoch_main", "indicator_id": "stoch", "params": {"k_length": 14, "k_smoothing": 3, "d_length": 3}},
                    {"key": "ema_mid", "indicator_id": "ema", "params": {"length": 50, "source": "close", "offset": 0}},
                    {"key": "adx_main", "indicator_id": "adx", "params": {"di_length": 14, "adx_smoothing": 14}},
                    {"key": "vwap_main", "indicator_id": "vwap", "params": {"anchor": "session", "source": "hlc3"}},
                ],
                "entry_rule": {
                    "type": "AND",
                    "children": [
                        {"type": "COMPARE", "left": "price.close", "op": "<=", "right": "bb_main.lower"},
                        {"type": "COMPARE", "left": "rsi_main.rsi", "op": "<", "right": 38},
                    ],
                },
                "exit_rule": {
                    "type": "OR",
                    "children": [
                        {"type": "COMPARE", "left": "price.close", "op": ">=", "right": "bb_main.basis"},
                        {"type": "COMPARE", "left": "rsi_main.rsi", "op": ">", "right": 68},
                    ],
                },
            },
        ),
    ]

    for name, desc, status_val, raw_defn in defaults:
        defn = validate_strategy_definition(raw_defn)
        strat = Strategy(name=name, description=desc, status=status_val)
        db.add(strat)
        db.flush()
        ver = StrategyVersion(
            strategy_id=strat.id,
            version_no=1,
            definition_json=defn,
            definition_hash=compute_definition_hash(defn),
            change_note="Initial seeded strategy version",
        )
        db.add(ver)
        db.flush()
        strat.current_version_id = ver.id

    db.commit()


def _serialize_version(v: StrategyVersion) -> dict[str, Any]:
    return {
        "id": v.id,
        "strategy_id": v.strategy_id,
        "version_no": v.version_no,
        "definition": v.definition_json,
        "definition_hash": v.definition_hash,
        "change_note": v.change_note,
        "created_at": _iso(v.created_at),
    }


def _serialize_strategy(db: Session, s: Strategy, include_versions: bool = False) -> dict[str, Any]:
    versions = (
        db.execute(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == s.id)
            .order_by(StrategyVersion.version_no.desc())
        )
        .scalars()
        .all()
    )
    current = next((v for v in versions if v.id == s.current_version_id), versions[0] if versions else None)
    data: dict[str, Any] = {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "status": s.status,
        "current_version_id": s.current_version_id,
        "current_version": _serialize_version(current) if current else None,
        "version_count": len(versions),
        "created_at": _iso(s.created_at),
        "updated_at": _iso(s.updated_at),
    }
    if include_versions:
        data["versions"] = [_serialize_version(v) for v in versions]
    return data


class StrategyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    description: str = Field(default="", max_length=1000)
    status: str = Field(default="Draft")
    definition: dict[str, Any]
    change_note: str = Field(default="Initial version", max_length=255)


class StrategyNewVersionRequest(BaseModel):
    definition: dict[str, Any]
    change_note: str = Field(default="Updated parameters/rules", max_length=255)


class StrategyStatusRequest(BaseModel):
    status: str


class StrategyEvaluateRequest(BaseModel):
    strategy_version_id: str | None = None
    definition: dict[str, Any] | None = None
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="15m", min_length=2, max_length=16)
    limit: int = Field(default=250, ge=50, le=1000)


@strategies_router.get("")
def list_strategies(db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_default_strategies(db)
    rows = db.execute(select(Strategy).order_by(Strategy.updated_at.desc())).scalars().all()
    return {"items": [_serialize_strategy(db, s, include_versions=True) for s in rows]}


@strategies_router.post("", status_code=status.HTTP_201_CREATED)
def create_strategy(
    payload: StrategyCreateRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    ensure_default_strategies(db)
    if payload.status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid strategy status '{payload.status}'")
    try:
        defn = validate_strategy_definition(payload.definition)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _, current_user = ctx
    strat = Strategy(
        owner_id=current_user.id if current_user else None,
        name=payload.name.strip(),
        description=payload.description.strip(),
        status=payload.status,
    )
    db.add(strat)
    db.flush()

    ver = StrategyVersion(
        strategy_id=strat.id,
        version_no=1,
        definition_json=defn,
        definition_hash=compute_definition_hash(defn),
        change_note=payload.change_note.strip() or "Initial version",
    )
    db.add(ver)
    db.flush()
    strat.current_version_id = ver.id

    if current_user is not None:
        append_audit_log(
            db,
            actor=current_user.email,
            action="strategy.created",
            entity=f"strategy:{strat.id}",
            payload={"name": strat.name, "version_no": 1, "hash": ver.definition_hash},
            owner_id=current_user.id,
        )

    db.commit()
    return _serialize_strategy(db, strat, include_versions=True)


@strategies_router.get("/{strategy_id}")
def get_strategy(strategy_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    strat = db.execute(select(Strategy).where(Strategy.id == strategy_id)).scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _serialize_strategy(db, strat, include_versions=True)


@strategies_router.post("/{strategy_id}/versions", status_code=status.HTTP_201_CREATED)
def create_strategy_version(
    strategy_id: str,
    payload: StrategyNewVersionRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    strat = db.execute(select(Strategy).where(Strategy.id == strategy_id)).scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        defn = validate_strategy_definition(payload.definition)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    latest = db.execute(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strat.id)
        .order_by(StrategyVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_no = (latest.version_no + 1) if latest else 1

    ver = StrategyVersion(
        strategy_id=strat.id,
        version_no=next_no,
        definition_json=defn,
        definition_hash=compute_definition_hash(defn),
        change_note=payload.change_note.strip() or f"Version {next_no}",
    )
    db.add(ver)
    db.flush()
    strat.current_version_id = ver.id
    strat.updated_at = utcnow()

    _, current_user = ctx
    if current_user is not None:
        append_audit_log(
            db,
            actor=current_user.email,
            action="strategy.version_created",
            entity=f"strategy:{strat.id}",
            payload={"version_no": next_no, "hash": ver.definition_hash},
            owner_id=current_user.id,
        )

    db.commit()
    return _serialize_strategy(db, strat, include_versions=True)


@strategies_router.patch("/{strategy_id}/status")
def update_strategy_status(
    strategy_id: str,
    payload: StrategyStatusRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid strategy status '{payload.status}'")
    strat = db.execute(select(Strategy).where(Strategy.id == strategy_id)).scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    strat.status = payload.status
    strat.updated_at = utcnow()
    db.commit()
    return _serialize_strategy(db, strat, include_versions=True)


@strategies_router.post("/evaluate")
def evaluate_strategy_endpoint(
    payload: StrategyEvaluateRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    raw_defn = payload.definition
    if payload.strategy_version_id:
        ver = db.execute(
            select(StrategyVersion).where(StrategyVersion.id == payload.strategy_version_id)
        ).scalar_one_or_none()
        if ver is None:
            raise HTTPException(status_code=404, detail="Strategy version not found")
        raw_defn = ver.definition_json

    if not raw_defn:
        raise HTTPException(status_code=400, detail="Provide strategy_version_id or definition")
    if payload.timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")

    try:
        defn = validate_strategy_definition(raw_defn)
        synced = sync_and_get_candles(
            db, client, symbol=payload.symbol, timeframe=payload.timeframe, limit=payload.limit
        )
        htf_map: dict[str, tuple[int, list[dict[str, Any]]]] = {}
        for inst in defn["indicators"]:
            tf_ov = inst.get("timeframe")
            if tf_ov and tf_ov in TIMEFRAME_SECONDS and tf_ov not in htf_map:
                htf_sync = sync_and_get_candles(db, client, symbol=payload.symbol, timeframe=tf_ov, limit=150)
                htf_map[tf_ov] = (TIMEFRAME_SECONDS[tf_ov], htf_sync["items"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MexcApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    res = evaluate_strategy(defn, synced["items"], htf_candles=htf_map or None)
    candles = synced["items"]
    entry_signals = res["entry_signals"]
    exit_signals = res["exit_signals"]

    recent_signals = []
    for i, bar in enumerate(candles):
        if entry_signals[i]:
            recent_signals.append({"time": bar["time"], "type": "entry", "price": bar["close"]})
        elif exit_signals[i]:
            recent_signals.append({"time": bar["time"], "type": "exit", "price": bar["close"]})

    return {
        "symbol": synced["symbol"],
        "timeframe": synced["timeframe"],
        "bars_evaluated": len(candles),
        "entry_count": sum(1 for x in entry_signals if x),
        "exit_count": sum(1 for x in exit_signals if x),
        "latest_confluence": res["confluence_scores"][-1] if res["confluence_scores"] else 0.0,
        "recent_signals": recent_signals[-25:],
    }
