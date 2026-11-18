from __future__ import annotations

import time
from datetime import timezone
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.router import get_optional_session_and_user
from app.db.models import (
    ApiCredential,
    LiveAuthorization,
    LiveOrder,
    LiveTrade,
    Notification,
    PaperAccount,
    PaperOrder,
    PaperTrade,
    RiskProfile,
    Strategy,
    StrategyVersion,
    Symbol,
    User,
    UserSession,
    utcnow,
)
from app.db.session import get_db
from app.services.audit import append_audit_log
from app.services.market_data import ensure_symbol
from app.services.mexc_provider import get_mexc_client
from engine.risk.engine import RiskEngine, RiskLimits, derive_client_order_id
from exchanges.mexc.market_client import MexcApiError, MexcMarketDataClient

trading_risk_router = APIRouter(prefix="/api/v1")
_risk_engine = RiskEngine()


def _iso(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def ensure_risk_profile(db: Session) -> RiskProfile:
    row = db.execute(select(RiskProfile).limit(1)).scalar_one_or_none()
    if row is not None:
        return row
    row = RiskProfile(
        name="Default Conservative Spot Profile",
        max_risk_per_trade_pct=Decimal("2.0"),
        max_daily_loss_pct=Decimal("5.0"),
        max_weekly_loss_pct=Decimal("10.0"),
        max_drawdown_pct=Decimal("15.0"),
        max_open_positions=5,
        max_asset_exposure_pct=Decimal("40.0"),
        cooldown_minutes=15,
        emergency_stop_active=False,
    )
    db.add(row)
    db.commit()
    return row


def ensure_paper_account(db: Session) -> PaperAccount:
    acc = db.execute(select(PaperAccount).limit(1)).scalar_one_or_none()
    if acc is not None:
        return acc
    acc = PaperAccount(
        name="APEX Paper Spot Account",
        initial_balance_usdt=Decimal("10000.0"),
        available_usdt=Decimal("10000.0"),
    )
    db.add(acc)
    db.commit()
    return acc


def _limits_from_profile(rp: RiskProfile) -> RiskLimits:
    return RiskLimits(
        max_risk_per_trade_pct=float(rp.max_risk_per_trade_pct),
        max_daily_loss_pct=float(rp.max_daily_loss_pct),
        max_weekly_loss_pct=float(rp.max_weekly_loss_pct),
        max_drawdown_pct=float(rp.max_drawdown_pct),
        max_open_positions=int(rp.max_open_positions),
        max_asset_exposure_pct=float(rp.max_asset_exposure_pct),
        cooldown_minutes=int(rp.cooldown_minutes),
        emergency_stop_active=bool(rp.emergency_stop_active),
    )


def _serialize_risk_profile(rp: RiskProfile) -> dict[str, Any]:
    return {
        "id": rp.id,
        "name": rp.name,
        "max_risk_per_trade_pct": float(rp.max_risk_per_trade_pct),
        "max_daily_loss_pct": float(rp.max_daily_loss_pct),
        "max_weekly_loss_pct": float(rp.max_weekly_loss_pct),
        "max_drawdown_pct": float(rp.max_drawdown_pct),
        "max_open_positions": int(rp.max_open_positions),
        "max_asset_exposure_pct": float(rp.max_asset_exposure_pct),
        "cooldown_minutes": int(rp.cooldown_minutes),
        "emergency_stop_active": bool(rp.emergency_stop_active),
        "updated_at": _iso(rp.updated_at),
    }


def _compute_positions_and_pnl(
    orders: list[Any],
    trades_by_order: dict[str, list[Any]],
    symbols_by_id: dict[int, Symbol],
    live_prices: dict[str, float],
) -> tuple[list[dict[str, Any]], float]:
    holdings: dict[str, dict[str, float]] = {}
    realized_pnl = 0.0

    for order in sorted(orders, key=lambda o: o.created_at):
        sym = symbols_by_id.get(order.symbol_id)
        if not sym:
            continue
        pair = sym.symbol
        pos = holdings.setdefault(pair, {"qty": 0.0, "cost_usdt": 0.0})
        for tr in trades_by_order.get(order.id, []):
            qty = float(tr.qty)
            px = float(tr.price)
            fee = float(tr.fee)
            if order.side.lower() == "buy":
                pos["qty"] += qty
                pos["cost_usdt"] += qty * px + fee
            else:
                if pos["qty"] > 1e-12:
                    avg_cost = pos["cost_usdt"] / pos["qty"]
                    sell_qty = min(qty, pos["qty"])
                    proceeds = sell_qty * px - fee
                    realized_pnl += proceeds - (sell_qty * avg_cost)
                    pos["qty"] = max(0.0, pos["qty"] - sell_qty)
                    pos["cost_usdt"] = max(0.0, pos["qty"] * avg_cost)

    positions: list[dict[str, Any]] = []
    for pair, pos in holdings.items():
        if pos["qty"] <= 1e-9:
            continue
        avg_entry = pos["cost_usdt"] / pos["qty"]
        mark_px = live_prices.get(pair, avg_entry)
        market_val = pos["qty"] * mark_px
        unrealized = market_val - pos["cost_usdt"]
        unrealized_pct = (unrealized / pos["cost_usdt"]) * 100.0 if pos["cost_usdt"] > 0 else 0.0
        positions.append(
            {
                "symbol": pair,
                "qty": round(pos["qty"], 8),
                "avg_entry_price": round(avg_entry, 6),
                "mark_price": round(mark_px, 6),
                "market_value_usdt": round(market_val, 2),
                "unrealized_pnl_usdt": round(unrealized, 2),
                "unrealized_pnl_pct": round(unrealized_pct, 2),
            }
        )

    return positions, round(realized_pnl, 2)


def _fetch_live_price_map(client: MexcMarketDataClient) -> dict[str, float]:
    try:
        rows = client.get_24h_tickers()
        prices: dict[str, float] = {}
        for r in rows:
            mexc_sym = str(r.get("mexc_symbol", ""))
            if mexc_sym.endswith("USDT"):
                base = mexc_sym[:-4]
                prices[f"{base}/USDT"] = float(r.get("last", 0.0))
        return prices
    except Exception:
        return {}


class RiskProfileUpdateRequest(BaseModel):
    max_risk_per_trade_pct: float = Field(gt=0.0, le=50.0)
    max_daily_loss_pct: float = Field(gt=0.0, le=90.0)
    max_weekly_loss_pct: float = Field(gt=0.0, le=95.0)
    max_drawdown_pct: float = Field(gt=0.0, le=95.0)
    max_open_positions: int = Field(ge=1, le=50)
    max_asset_exposure_pct: float = Field(gt=0.0, le=100.0)
    cooldown_minutes: int = Field(ge=0, le=1440)


class EmergencyStopRequest(BaseModel):
    active: bool


class OrderSubmitRequest(BaseModel):
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    side: Literal["buy", "sell"]
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    qty: float = Field(gt=0.0)
    price: float | None = Field(default=None, gt=0.0)
    stop_loss_pct: float = Field(default=1.5, gt=0.0, le=50.0)


class LiveAuthorizeRequest(BaseModel):
    strategy_version_id: str
    capital_mode: Literal["fixed_usdt", "pct_portfolio"] = "fixed_usdt"
    capital_value: float = Field(gt=0.0)
    scope: str = Field(default="BTC/USDT Spot", min_length=3, max_length=120)


class LiveOrderSubmitRequest(OrderSubmitRequest):
    authorization_id: str
    candle_time: int | None = None


@trading_risk_router.get("/risk/profile")
def get_risk_profile(db: Session = Depends(get_db)) -> dict[str, Any]:
    rp = ensure_risk_profile(db)
    return _serialize_risk_profile(rp)


@trading_risk_router.put("/risk/profile")
def update_risk_profile(
    payload: RiskProfileUpdateRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    rp = ensure_risk_profile(db)
    rp.max_risk_per_trade_pct = Decimal(str(payload.max_risk_per_trade_pct))
    rp.max_daily_loss_pct = Decimal(str(payload.max_daily_loss_pct))
    rp.max_weekly_loss_pct = Decimal(str(payload.max_weekly_loss_pct))
    rp.max_drawdown_pct = Decimal(str(payload.max_drawdown_pct))
    rp.max_open_positions = payload.max_open_positions
    rp.max_asset_exposure_pct = Decimal(str(payload.max_asset_exposure_pct))
    rp.cooldown_minutes = payload.cooldown_minutes
    rp.updated_at = utcnow()

    _, current_user = ctx
    if current_user is not None:
        append_audit_log(
            db,
            actor=current_user.email,
            action="risk.profile_updated",
            entity=f"risk_profile:{rp.id}",
            payload=payload.model_dump(),
            owner_id=current_user.id,
        )
    db.commit()
    return _serialize_risk_profile(rp)


@trading_risk_router.post("/risk/emergency-stop")
def toggle_emergency_stop(
    payload: EmergencyStopRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    rp = ensure_risk_profile(db)
    rp.emergency_stop_active = payload.active
    rp.updated_at = utcnow()

    revoked_count = 0
    if payload.active:
        active_auths = db.execute(
            select(LiveAuthorization).where(LiveAuthorization.revoked_at.is_(None))
        ).scalars().all()
        for auth in active_auths:
            auth.revoked_at = utcnow()
            revoked_count += 1

    _, current_user = ctx
    actor = current_user.email if current_user else "owner"
    append_audit_log(
        db,
        actor=actor,
        action="risk.emergency_stop",
        entity=f"risk_profile:{rp.id}",
        payload={"active": payload.active, "revoked_authorizations": revoked_count},
        owner_id=current_user.id if current_user else None,
    )
    db.add(
        Notification(
            owner_id=current_user.id if current_user else None,
            level="error" if payload.active else "info",
            category="risk",
            title="Emergency Stop ACTIVATED" if payload.active else "Emergency Stop cleared",
            body=(
                f"All trading blocked and {revoked_count} live authorizations revoked."
                if payload.active
                else "Manual orders may resume after authorization review."
            ),
        )
    )
    db.commit()
    return {
        "emergency_stop_active": rp.emergency_stop_active,
        "revoked_authorizations": revoked_count,
    }


@trading_risk_router.get("/paper/overview")
def get_paper_overview(
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    acc = ensure_paper_account(db)
    orders = (
        db.execute(
            select(PaperOrder)
            .where(PaperOrder.paper_account_id == acc.id)
            .order_by(PaperOrder.created_at.desc())
        )
        .scalars()
        .all()
    )
    trades = db.execute(select(PaperTrade).order_by(PaperTrade.executed_at.desc())).scalars().all()
    symbols_by_id = {s.id: s for s in db.execute(select(Symbol)).scalars().all()}

    trades_by_order: dict[str, list[PaperTrade]] = {}
    for tr in trades:
        trades_by_order.setdefault(tr.paper_order_id, []).append(tr)

    live_prices = _fetch_live_price_map(client)
    positions, realized_pnl = _compute_positions_and_pnl(orders, trades_by_order, symbols_by_id, live_prices)

    positions_val = sum(p["market_value_usdt"] for p in positions)
    unrealized_pnl = sum(p["unrealized_pnl_usdt"] for p in positions)
    available_usdt = float(acc.available_usdt)
    total_equity = available_usdt + positions_val

    return {
        "account": {
            "id": acc.id,
            "name": acc.name,
            "initial_balance_usdt": round(float(acc.initial_balance_usdt), 2),
            "available_usdt": round(available_usdt, 2),
            "positions_value_usdt": round(positions_val, 2),
            "total_equity_usdt": round(total_equity, 2),
            "realized_pnl_usdt": realized_pnl,
            "unrealized_pnl_usdt": round(unrealized_pnl, 2),
        },
        "positions": positions,
        "orders": [
            {
                "id": o.id,
                "client_order_id": o.client_order_id,
                "symbol": symbols_by_id[o.symbol_id].symbol if o.symbol_id in symbols_by_id else str(o.symbol_id),
                "side": o.side,
                "order_type": o.order_type,
                "qty": float(o.qty),
                "price": float(o.price) if o.price is not None else None,
                "status": o.status,
                "created_at": _iso(o.created_at),
            }
            for o in orders[:50]
        ],
        "trades": [
            {
                "id": tr.id,
                "paper_order_id": tr.paper_order_id,
                "price": float(tr.price),
                "qty": float(tr.qty),
                "fee": float(tr.fee),
                "fee_asset": tr.fee_asset,
                "executed_at": _iso(tr.executed_at),
            }
            for tr in trades[:50]
        ],
    }


@trading_risk_router.post("/paper/orders", status_code=status.HTTP_201_CREATED)
def submit_paper_order(
    payload: OrderSubmitRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    acc = ensure_paper_account(db)
    rp = ensure_risk_profile(db)
    clean_symbol = payload.symbol.strip().upper()
    sym_row = ensure_symbol(db, client, clean_symbol)

    live_prices = _fetch_live_price_map(client)
    exec_price = float(payload.price) if payload.price is not None else live_prices.get(clean_symbol, 0.0)
    if exec_price <= 0:
        raise HTTPException(status_code=400, detail=f"Unable to determine live price for {clean_symbol}")

    orders = (
        db.execute(select(PaperOrder).where(PaperOrder.paper_account_id == acc.id))
        .scalars()
        .all()
    )
    trades_all = db.execute(select(PaperTrade)).scalars().all()
    trades_by_order: dict[str, list[PaperTrade]] = {}
    for tr in trades_all:
        trades_by_order.setdefault(tr.paper_order_id, []).append(tr)
    symbols_by_id = {s.id: s for s in db.execute(select(Symbol)).scalars().all()}
    positions, _ = _compute_positions_and_pnl(orders, trades_by_order, symbols_by_id, live_prices)

    held_pos = next((p for p in positions if p["symbol"] == clean_symbol), None)
    held_qty = held_pos["qty"] if held_pos else 0.0
    held_val = held_pos["market_value_usdt"] if held_pos else 0.0
    total_equity = float(acc.available_usdt) + sum(p["market_value_usdt"] for p in positions)

    gate = _risk_engine.evaluate_order(
        limits=_limits_from_profile(rp),
        symbol=clean_symbol,
        side=payload.side,
        qty=payload.qty,
        price=exec_price,
        available_usdt=float(acc.available_usdt),
        total_equity_usdt=total_equity,
        held_asset_qty=held_qty,
        open_positions_count=len(positions),
        existing_asset_usdt=held_val,
        stop_loss_pct=payload.stop_loss_pct,
    )
    if not gate["approved"]:
        raise HTTPException(status_code=400, detail=gate["reason"])

    fee_rate = 0.001
    gross_usdt = payload.qty * exec_price
    fee_usdt = gross_usdt * fee_rate
    if payload.side == "buy":
        total_cost = gross_usdt + fee_usdt
        if total_cost > float(acc.available_usdt):
            raise HTTPException(status_code=400, detail="INSUFFICIENT_USDT_BALANCE")
        acc.available_usdt = Decimal(str(round(float(acc.available_usdt) - total_cost, 10)))
    else:
        net_proceeds = max(0.0, gross_usdt - fee_usdt)
        acc.available_usdt = Decimal(str(round(float(acc.available_usdt) + net_proceeds, 10)))

    client_oid = f"paper-{int(time.time() * 1000)}-{clean_symbol.replace('/', '')}"
    order = PaperOrder(
        paper_account_id=acc.id,
        client_order_id=client_oid,
        symbol_id=sym_row.id,
        side=payload.side,
        order_type=payload.order_type,
        qty=Decimal(str(payload.qty)),
        price=Decimal(str(exec_price)),
        status="FILLED",
    )
    db.add(order)
    db.flush()

    trade = PaperTrade(
        paper_order_id=order.id,
        price=Decimal(str(exec_price)),
        qty=Decimal(str(payload.qty)),
        fee=Decimal(str(round(fee_usdt, 10))),
        fee_asset="USDT",
    )
    db.add(trade)
    db.commit()

    return {
        "order_id": order.id,
        "client_order_id": order.client_order_id,
        "symbol": clean_symbol,
        "side": order.side,
        "qty": float(order.qty),
        "price": float(order.price),
        "fee_usdt": round(fee_usdt, 4),
        "status": order.status,
    }


@trading_risk_router.post("/paper/reset")
def reset_paper_account(db: Session = Depends(get_db)) -> dict[str, Any]:
    acc = ensure_paper_account(db)
    orders = db.execute(select(PaperOrder).where(PaperOrder.paper_account_id == acc.id)).scalars().all()
    for o in orders:
        db.delete(o)
    acc.available_usdt = acc.initial_balance_usdt
    acc.updated_at = utcnow()
    db.commit()
    return {"ok": True, "available_usdt": float(acc.available_usdt)}


@trading_risk_router.get("/live/overview")
def get_live_overview(
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    rp = ensure_risk_profile(db)
    auths = (
        db.execute(select(LiveAuthorization).order_by(LiveAuthorization.granted_at.desc()))
        .scalars()
        .all()
    )
    orders = db.execute(select(LiveOrder).order_by(LiveOrder.created_at.desc()).limit(50)).scalars().all()
    trades = db.execute(select(LiveTrade).order_by(LiveTrade.executed_at.desc()).limit(50)).scalars().all()
    symbols_by_id = {s.id: s for s in db.execute(select(Symbol)).scalars().all()}
    cred_count = db.execute(
        select(func.count(ApiCredential.id)).where(
            ApiCredential.provider_type == "exchange",
            ApiCredential.provider_name == "mexc",
        )
    ).scalar_one()

    trades_by_order: dict[str, list[LiveTrade]] = {}
    for tr in trades:
        trades_by_order.setdefault(tr.live_order_id, []).append(tr)
    live_prices = _fetch_live_price_map(client)
    positions, realized_pnl = _compute_positions_and_pnl(orders, trades_by_order, symbols_by_id, live_prices)

    return {
        "exchange_credentials_configured": int(cred_count) > 0,
        "local_host_warning": (
            "Automated trading and platform-side SL/TP monitoring pause immediately if your local Windows machine sleeps or shuts down."
        ),
        "risk_profile": _serialize_risk_profile(rp),
        "realized_pnl_usdt": realized_pnl,
        "positions": positions,
        "authorizations": [
            {
                "id": a.id,
                "strategy_version_id": a.strategy_version_id,
                "capital_mode": a.capital_mode,
                "capital_value": float(a.capital_value),
                "scope": a.scope,
                "active": a.revoked_at is None,
                "granted_at": _iso(a.granted_at),
                "revoked_at": _iso(a.revoked_at) if a.revoked_at else None,
            }
            for a in auths
        ],
        "orders": [
            {
                "id": o.id,
                "client_order_id": o.client_order_id,
                "symbol": symbols_by_id[o.symbol_id].symbol if o.symbol_id in symbols_by_id else str(o.symbol_id),
                "side": o.side,
                "order_type": o.order_type,
                "qty": float(o.qty),
                "price": float(o.price) if o.price is not None else None,
                "status": o.status,
                "risk_approval_token": o.risk_approval_token[:16] + "…",
                "created_at": _iso(o.created_at),
            }
            for o in orders
        ],
        "trades": [
            {
                "id": tr.id,
                "live_order_id": tr.live_order_id,
                "exchange_trade_id": tr.exchange_trade_id,
                "price": float(tr.price),
                "qty": float(tr.qty),
                "fee": float(tr.fee),
                "fee_asset": tr.fee_asset,
                "executed_at": _iso(tr.executed_at),
            }
            for tr in trades
        ],
    }


@trading_risk_router.post("/live/authorize", status_code=status.HTTP_201_CREATED)
def authorize_live_strategy(
    payload: LiveAuthorizeRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    rp = ensure_risk_profile(db)
    if rp.emergency_stop_active:
        raise HTTPException(status_code=400, detail="EMERGENCY_STOP_ACTIVE")

    ver = db.execute(
        select(StrategyVersion).where(StrategyVersion.id == payload.strategy_version_id)
    ).scalar_one_or_none()
    if ver is None:
        raise HTTPException(status_code=404, detail="Strategy version not found")
    strat = db.execute(select(Strategy).where(Strategy.id == ver.strategy_id)).scalar_one_or_none()
    if strat is None or strat.status not in {"Approved", "Live"}:
        raise HTTPException(
            status_code=400,
            detail="Strategy must be in 'Approved' or 'Live' status before Live Authorization",
        )

    _, current_user = ctx
    auth = LiveAuthorization(
        owner_id=current_user.id if current_user else None,
        strategy_version_id=ver.id,
        capital_mode=payload.capital_mode,
        capital_value=Decimal(str(payload.capital_value)),
        risk_profile_id=rp.id,
        scope=payload.scope.strip(),
    )
    db.add(auth)
    strat.status = "Live"
    db.flush()

    append_audit_log(
        db,
        actor=current_user.email if current_user else "owner",
        action="live.authorization_granted",
        entity=f"live_authorization:{auth.id}",
        payload={"strategy_version_id": ver.id, "scope": auth.scope, "capital_value": float(auth.capital_value)},
        owner_id=current_user.id if current_user else None,
    )
    db.add(
        Notification(
            owner_id=current_user.id if current_user else None,
            level="warning",
            category="live_trading",
            title=f"Live Authorization granted ({strat.name})",
            body=f"Scope: {auth.scope} · Capital: {auth.capital_value}",
        )
    )
    db.commit()

    return {
        "id": auth.id,
        "strategy_version_id": auth.strategy_version_id,
        "scope": auth.scope,
        "capital_value": float(auth.capital_value),
        "active": True,
        "granted_at": _iso(auth.granted_at),
    }


@trading_risk_router.post("/live/revoke/{auth_id}")
def revoke_live_authorization(
    auth_id: str,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    auth = db.execute(select(LiveAuthorization).where(LiveAuthorization.id == auth_id)).scalar_one_or_none()
    if auth is None:
        raise HTTPException(status_code=404, detail="Authorization not found")
    auth.revoked_at = utcnow()
    _, current_user = ctx
    append_audit_log(
        db,
        actor=current_user.email if current_user else "owner",
        action="live.authorization_revoked",
        entity=f"live_authorization:{auth.id}",
        payload={},
        owner_id=current_user.id if current_user else None,
    )
    db.commit()
    return {"ok": True, "id": auth.id}


@trading_risk_router.post("/live/orders", status_code=status.HTTP_201_CREATED)
def submit_live_order(
    payload: LiveOrderSubmitRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    auth = db.execute(
        select(LiveAuthorization).where(
            LiveAuthorization.id == payload.authorization_id,
            LiveAuthorization.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if auth is None:
        raise HTTPException(status_code=403, detail="LIVE_AUTHORIZATION_REQUIRED")

    rp = ensure_risk_profile(db)
    clean_symbol = payload.symbol.strip().upper()
    sym_row = ensure_symbol(db, client, clean_symbol)

    live_prices = _fetch_live_price_map(client)
    exec_price = float(payload.price) if payload.price is not None else live_prices.get(clean_symbol, 0.0)
    if exec_price <= 0:
        raise HTTPException(status_code=400, detail=f"Unable to determine live price for {clean_symbol}")

    cap_budget = float(auth.capital_value)
    gate = _risk_engine.evaluate_order(
        limits=_limits_from_profile(rp),
        symbol=clean_symbol,
        side=payload.side,
        qty=payload.qty,
        price=exec_price,
        available_usdt=cap_budget,
        total_equity_usdt=max(cap_budget, 1000.0),
        held_asset_qty=payload.qty if payload.side == "sell" else 0.0,
        open_positions_count=0,
        existing_asset_usdt=0.0,
        stop_loss_pct=payload.stop_loss_pct,
    )
    if not gate["approved"]:
        raise HTTPException(status_code=400, detail=gate["reason"])

    candle_ts = payload.candle_time if payload.candle_time is not None else int(time.time())
    client_oid = derive_client_order_id(auth.strategy_version_id, clean_symbol, candle_ts, payload.side)

    existing = db.execute(
        select(LiveOrder).where(LiveOrder.client_order_id == client_oid)
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "order_id": existing.id,
            "client_order_id": existing.client_order_id,
            "status": existing.status,
            "duplicate_prevented": True,
        }

    _, current_user = ctx
    # Write-before-send guarantee: persist PENDING_SUBMIT before touching exchange
    order = LiveOrder(
        owner_id=current_user.id if current_user else None,
        authorization_id=auth.id,
        client_order_id=client_oid,
        symbol_id=sym_row.id,
        side=payload.side,
        order_type=payload.order_type,
        qty=Decimal(str(payload.qty)),
        price=Decimal(str(exec_price)),
        status="PENDING_SUBMIT",
        risk_approval_token=gate["risk_approval_token"],
    )
    db.add(order)
    db.flush()

    append_audit_log(
        db,
        actor=current_user.email if current_user else "owner",
        action="live.order_staged",
        entity=f"live_order:{order.id}",
        payload={"client_order_id": client_oid, "symbol": clean_symbol, "side": payload.side, "qty": payload.qty},
        owner_id=current_user.id if current_user else None,
    )
    db.commit()

    return {
        "order_id": order.id,
        "client_order_id": order.client_order_id,
        "status": order.status,
        "duplicate_prevented": False,
        "risk_approval_token": order.risk_approval_token[:16] + "…",
    }
