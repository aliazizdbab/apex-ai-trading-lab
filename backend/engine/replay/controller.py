from __future__ import annotations

from typing import Any


def build_replay_view(
    candles: list[dict[str, Any]],
    cursor_index: int,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Slice candles strictly up to cursor_index so future candles are never transmitted."""
    if not candles:
        return {
            "cursor_index": 0,
            "total_bars": 0,
            "visible_candles": [],
            "current_bar": None,
            "state": state,
        }

    clamped_idx = max(0, min(int(cursor_index), len(candles) - 1))
    visible = candles[: clamped_idx + 1]
    current_bar = visible[-1]
    mark_price = float(current_bar["close"])

    cash = float(state.get("cash_usdt", 10000.0))
    pos_qty = float(state.get("position_qty", 0.0))
    avg_entry = float(state.get("avg_entry_price", 0.0))
    realized = float(state.get("realized_pnl_usdt", 0.0))

    unrealized = (mark_price - avg_entry) * pos_qty if pos_qty > 0 else 0.0
    equity = cash + (pos_qty * mark_price)

    enriched_state = {
        **state,
        "cash_usdt": round(cash, 4),
        "position_qty": round(pos_qty, 8),
        "avg_entry_price": round(avg_entry, 6),
        "realized_pnl_usdt": round(realized, 4),
        "unrealized_pnl_usdt": round(unrealized, 4),
        "total_equity_usdt": round(equity, 4),
    }

    return {
        "cursor_index": clamped_idx,
        "total_bars": len(candles),
        "visible_candles": visible,
        "current_bar": current_bar,
        "state": enriched_state,
    }


def apply_replay_order(
    candles: list[dict[str, Any]],
    cursor_index: int,
    state: dict[str, Any],
    side: str,
    qty: float,
    fee_pct: float = 0.1,
) -> dict[str, Any]:
    """Execute a simulated Spot market order strictly at the current replay bar close price."""
    if not candles:
        raise ValueError("Replay session has no candles")
    clamped_idx = max(0, min(int(cursor_index), len(candles) - 1))
    bar = candles[clamped_idx]
    price = float(bar["close"])
    clean_side = side.strip().lower()
    if clean_side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")
    if qty <= 0:
        raise ValueError("qty must be positive")

    fee_rate = fee_pct / 100.0
    cash = float(state.get("cash_usdt", 10000.0))
    pos_qty = float(state.get("position_qty", 0.0))
    avg_entry = float(state.get("avg_entry_price", 0.0))
    realized = float(state.get("realized_pnl_usdt", 0.0))
    trades = list(state.get("trades", []))

    if clean_side == "buy":
        gross = qty * price
        fee = gross * fee_rate
        total_cost = gross + fee
        if total_cost > cash:
            raise ValueError(f"Insufficient replay cash: need {total_cost:.2f}, have {cash:.2f}")
        new_qty = pos_qty + qty
        avg_entry = ((pos_qty * avg_entry) + total_cost) / new_qty if new_qty > 0 else 0.0
        pos_qty = new_qty
        cash -= total_cost
    else:
        if qty > pos_qty + 1e-12:
            raise ValueError(f"Insufficient replay position: need {qty}, hold {pos_qty}")
        sell_qty = min(qty, pos_qty)
        gross = sell_qty * price
        fee = gross * fee_rate
        net = gross - fee
        pnl = net - (sell_qty * avg_entry)
        realized += pnl
        cash += net
        pos_qty = max(0.0, pos_qty - sell_qty)
        if pos_qty < 1e-12:
            pos_qty = 0.0
            avg_entry = 0.0

    trades.append(
        {
            "time": int(bar["time"]),
            "side": clean_side,
            "price": round(price, 6),
            "qty": round(qty, 8),
        }
    )

    return {
        "cash_usdt": round(cash, 4),
        "position_qty": round(pos_qty, 8),
        "avg_entry_price": round(avg_entry, 6),
        "realized_pnl_usdt": round(realized, 4),
        "trades": trades,
    }
