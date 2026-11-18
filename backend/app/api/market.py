from __future__ import annotations

from datetime import timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.router import get_optional_session_and_user
from app.db.models import ApiCredential, CandleCoverage, Symbol, User, UserSession
from app.db.session import get_db
from app.services.audit import append_audit_log
from app.services.market_data import (
    AGGREGATED_TIMEFRAMES,
    DEFAULT_SPOT_SYMBOLS,
    NATIVE_MEXC_INTERVALS,
    TIMEFRAME_SECONDS,
    ensure_default_symbols,
    sync_and_get_candles,
)
from app.services.mexc_provider import get_mexc_client, get_ws_manager
from exchanges.mexc.market_client import MexcApiError, MexcMarketDataClient

market_router = APIRouter(prefix="/api/v1")


class BackfillRequest(BaseModel):
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="15m", min_length=2, max_length=8)
    bars: int = Field(default=500, ge=50, le=1500)


@market_router.get("/market/tickers")
def get_market_tickers(
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    try:
        rows = client.get_24h_tickers(DEFAULT_SPOT_SYMBOLS)
    except MexcApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    rows.sort(key=lambda r: r["volume24h"], reverse=True)
    return {
        "exchange": "mexc",
        "source": "mexc_live",
        "items": rows,
    }


@market_router.get("/market/candles")
def get_market_candles(
    symbol: str = Query(default="BTC/USDT", min_length=3, max_length=32),
    timeframe: str = Query(default="15m", min_length=2, max_length=8),
    limit: int = Query(default=250, ge=10, le=1500),
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    if timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported timeframe '{timeframe}'",
        )
    try:
        return sync_and_get_candles(db, client, symbol=symbol, timeframe=timeframe, limit=limit)
    except MexcApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@market_router.get("/market/orderbook")
def get_market_orderbook(
    symbol: str = Query(default="BTC/USDT", min_length=3, max_length=32),
    limit: int = Query(default=15, ge=5, le=50),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    clean_symbol = symbol.strip().upper()
    try:
        book = client.get_order_book(clean_symbol, limit=limit)
    except MexcApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return {"symbol": clean_symbol, "source": "mexc_live", **book}


@market_router.get("/market/trades")
def get_market_trades(
    symbol: str = Query(default="BTC/USDT", min_length=3, max_length=32),
    limit: int = Query(default=25, ge=1, le=100),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    clean_symbol = symbol.strip().upper()
    try:
        trades = client.get_recent_trades(clean_symbol, limit=limit)
    except MexcApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return {"symbol": clean_symbol, "source": "mexc_live", "items": trades}


@market_router.get("/market/coverage")
def get_market_coverage(db: Session = Depends(get_db)) -> dict[str, Any]:
    symbols = db.execute(select(Symbol).order_by(Symbol.symbol.asc())).scalars().all()
    sym_by_id = {s.id: s for s in symbols}
    coverages = db.execute(
        select(CandleCoverage).order_by(CandleCoverage.validated_at.desc())
    ).scalars().all()

    def _iso(dt):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()

    return {
        "symbols": [
            {
                "id": s.id,
                "symbol": s.symbol,
                "price_precision": s.price_precision,
                "qty_precision": s.qty_precision,
                "min_qty": str(s.min_qty),
                "min_notional": str(s.min_notional),
                "status": s.status,
            }
            for s in symbols
        ],
        "coverage": [
            {
                "id": c.id,
                "symbol": sym_by_id[c.symbol_id].symbol if c.symbol_id in sym_by_id else str(c.symbol_id),
                "timeframe": c.timeframe,
                "from_ts": _iso(c.from_ts),
                "to_ts": _iso(c.to_ts),
                "validated_at": _iso(c.validated_at),
                "gap_count": c.gap_count,
            }
            for c in coverages
        ],
    }


@market_router.post("/market/backfill")
def backfill_market_candles(
    payload: BackfillRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    if payload.timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported timeframe '{payload.timeframe}'",
        )

    try:
        result = sync_and_get_candles(
            db,
            client,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            limit=payload.bars,
        )
    except MexcApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    _, current_user = ctx
    if current_user is not None:
        append_audit_log(
            db,
            actor=current_user.email,
            action="market.backfill",
            entity=f"{result['symbol']}:{result['timeframe']}",
            payload={
                "source": result["source"],
                "total_bars": result["quality"]["total_bars"],
                "gap_count": result["quality"]["gap_count"],
                "data_snapshot_hash": result["quality"]["data_snapshot_hash"],
            },
            owner_id=current_user.id,
        )
        db.commit()

    return {
        "symbol": result["symbol"],
        "timeframe": result["timeframe"],
        "source": result["source"],
        "quality": result["quality"],
    }


@market_router.get("/exchanges/mexc/status")
def get_mexc_exchange_status(
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    cred_count = db.execute(
        select(func.count(ApiCredential.id)).where(
            ApiCredential.provider_type == "exchange",
            ApiCredential.provider_name == "mexc",
        )
    ).scalar_one()

    server_time_ms: int | None = None
    latency_ms: float | None = None
    rules_sample: list[dict[str, Any]] = []
    conn_status = "connected"
    error_msg: str | None = None

    try:
        server_time_ms, latency_ms = client.get_server_time()
        synced = ensure_default_symbols(db, client)
        rules_sample = [
            {
                "symbol": s.symbol,
                "price_precision": s.price_precision,
                "qty_precision": s.qty_precision,
                "min_qty": str(s.min_qty),
                "min_notional": str(s.min_notional),
                "status": s.status,
            }
            for s in synced[:6]
        ]
    except MexcApiError as exc:
        conn_status = "error"
        error_msg = str(exc)

    return {
        "exchange": "mexc",
        "scope": "Spot only (no Futures/Margin/Withdrawals)",
        "status": conn_status,
        "error": error_msg,
        "server_time_ms": server_time_ms,
        "latency_ms": latency_ms,
        "stored_credentials_count": int(cred_count),
        "rate_limiter": client.rate_limiter.status(),
        "ws_manager": get_ws_manager().snapshot_state(),
        "supported_order_types": ["LIMIT", "MARKET", "LIMIT_MAKER"],
        "platform_sl_tp_required": True,
        "platform_sl_tp_note": (
            "MEXC Spot supports LIMIT, MARKET, and LIMIT_MAKER natively. "
            "Stop-Loss / Take-Profit protection is managed by the APEX platform engine and pauses if the local host sleeps."
        ),
        "timeframes": [
            {
                "id": tf,
                "mode": "native" if tf in NATIVE_MEXC_INTERVALS else "aggregated",
                "mexc_interval": NATIVE_MEXC_INTERVALS.get(tf),
                "aggregated_from": AGGREGATED_TIMEFRAMES[tf][0] if tf in AGGREGATED_TIMEFRAMES else None,
            }
            for tf in TIMEFRAME_SECONDS
        ],
        "symbol_rules_sample": rules_sample,
    }
