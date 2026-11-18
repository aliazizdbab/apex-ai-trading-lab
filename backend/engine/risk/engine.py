from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RiskLimits:
    """Owner-configured capital protection limits (immutable by AI)."""

    max_risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    max_weekly_loss_pct: float = 10.0
    max_drawdown_pct: float = 15.0
    max_open_positions: int = 5
    max_asset_exposure_pct: float = 40.0
    cooldown_minutes: int = 15
    emergency_stop_active: bool = False


def derive_client_order_id(
    strategy_version_id: str,
    symbol: str,
    candle_time: int,
    side: str,
) -> str:
    """Derive a deterministic idempotent client_order_id from signal identity."""
    raw = f"{strategy_version_id}|{symbol.upper()}|{int(candle_time)}|{side.lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"apex-{digest}"


class RiskEngine:
    """Independent pre-trade gate issuing short-lived approval tokens."""

    def __init__(self, signing_key: bytes = b"apex-local-risk-gate") -> None:
        self._signing_key = signing_key

    def _issue_token(self, symbol: str, side: str, qty: float, price: float) -> str:
        msg = f"{symbol.upper()}|{side.lower()}|{qty:.8f}|{price:.8f}".encode("utf-8")
        return hmac.new(self._signing_key, msg, hashlib.sha256).hexdigest()

    def evaluate_order(
        self,
        *,
        limits: RiskLimits,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        available_usdt: float,
        total_equity_usdt: float,
        held_asset_qty: float = 0.0,
        open_positions_count: int = 0,
        existing_asset_usdt: float = 0.0,
        stop_loss_pct: float = 2.0,
        daily_loss_pct: float = 0.0,
        weekly_loss_pct: float = 0.0,
        drawdown_pct: float = 0.0,
        minutes_since_last_loss: float = 9999.0,
    ) -> dict[str, Any]:
        """Evaluate an OrderIntent against all risk constraints."""
        if limits.emergency_stop_active:
            return {"approved": False, "reason": "EMERGENCY_STOP_ACTIVE", "risk_approval_token": None}

        clean_side = side.strip().lower()
        if clean_side not in {"buy", "sell"}:
            return {"approved": False, "reason": "INVALID_SIDE", "risk_approval_token": None}

        if qty <= 0 or price <= 0:
            return {"approved": False, "reason": "INVALID_QTY_OR_PRICE", "risk_approval_token": None}

        if daily_loss_pct >= limits.max_daily_loss_pct:
            return {"approved": False, "reason": "DAILY_LOSS_LIMIT_REACHED", "risk_approval_token": None}

        if weekly_loss_pct >= limits.max_weekly_loss_pct:
            return {"approved": False, "reason": "WEEKLY_LOSS_LIMIT_REACHED", "risk_approval_token": None}

        if drawdown_pct >= limits.max_drawdown_pct:
            return {"approved": False, "reason": "MAX_DRAWDOWN_REACHED", "risk_approval_token": None}

        order_notional = qty * price

        if clean_side == "sell":
            if qty > held_asset_qty + 1e-12:
                return {"approved": False, "reason": "INSUFFICIENT_ASSET_BALANCE", "risk_approval_token": None}
            return {
                "approved": True,
                "reason": None,
                "risk_approval_token": self._issue_token(symbol, clean_side, qty, price),
            }

        # Buy-side checks
        if order_notional > available_usdt:
            return {"approved": False, "reason": "INSUFFICIENT_USDT_BALANCE", "risk_approval_token": None}

        if limits.cooldown_minutes > 0 and minutes_since_last_loss < limits.cooldown_minutes:
            return {"approved": False, "reason": "COOLDOWN_ACTIVE", "risk_approval_token": None}

        if held_asset_qty <= 1e-12 and open_positions_count >= limits.max_open_positions:
            return {"approved": False, "reason": "MAX_OPEN_POSITIONS_REACHED", "risk_approval_token": None}

        if total_equity_usdt > 0:
            exposure_pct = ((existing_asset_usdt + order_notional) / total_equity_usdt) * 100.0
            if exposure_pct > limits.max_asset_exposure_pct:
                return {
                    "approved": False,
                    "reason": f"ASSET_EXPOSURE_EXCEEDED ({exposure_pct:.1f}% > {limits.max_asset_exposure_pct:.1f}%)",
                    "risk_approval_token": None,
                }

            trade_risk_usdt = order_notional * (max(0.1, stop_loss_pct) / 100.0)
            trade_risk_pct = (trade_risk_usdt / total_equity_usdt) * 100.0
            if trade_risk_pct > limits.max_risk_per_trade_pct:
                return {
                    "approved": False,
                    "reason": f"TRADE_RISK_EXCEEDED ({trade_risk_pct:.2f}% > {limits.max_risk_per_trade_pct:.2f}%)",
                    "risk_approval_token": None,
                }

        return {
            "approved": True,
            "reason": None,
            "risk_approval_token": self._issue_token(symbol, clean_side, qty, price),
        }
