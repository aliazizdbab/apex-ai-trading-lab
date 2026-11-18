from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any


def to_mexc_symbol(symbol: str) -> str:
    """Convert display pair like 'BTC/USDT' to MEXC symbol 'BTCUSDT'."""
    return symbol.strip().upper().replace("/", "").replace("-", "")


def _count_decimals(value_str: str | None, fallback: int = 8) -> int:
    if not value_str:
        return fallback
    cleaned = str(value_str).strip()
    if "." not in cleaned:
        return 0
    frac = cleaned.rstrip("0").split(".", 1)[1]
    return len(frac)


def _safe_decimal(value: Any, default: str) -> Decimal:
    try:
        d = Decimal(str(value))
        return d if d > 0 else Decimal(default)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


@dataclass(frozen=True)
class SymbolOrderRules:
    """Exchange trading precision and minimum order rules for a Spot pair."""

    symbol: str
    mexc_symbol: str
    base: str
    quote: str
    price_precision: int
    qty_precision: int
    min_qty: Decimal
    min_notional: Decimal
    order_types: tuple[str, ...]
    status: str


def parse_mexc_symbol_info(raw: dict[str, Any]) -> SymbolOrderRules:
    """Parse an entry from MEXC /api/v3/exchangeInfo into normalized SymbolOrderRules."""
    base = str(raw["baseAsset"]).upper()
    quote = str(raw["quoteAsset"]).upper()
    mexc_symbol = str(raw["symbol"]).upper()
    display_symbol = f"{base}/{quote}"

    price_precision = int(raw.get("quotePrecision", raw.get("quoteAssetPrecision", 2)))
    base_size_str = raw.get("baseSizePrecision")
    if base_size_str is not None and str(base_size_str).strip():
        qty_precision = _count_decimals(str(base_size_str), fallback=int(raw.get("baseAssetPrecision", 6)))
        min_qty = _safe_decimal(base_size_str, "0.000001")
    else:
        qty_precision = int(raw.get("baseAssetPrecision", 6))
        min_qty = Decimal("10") ** (-qty_precision)

    min_notional = _safe_decimal(raw.get("quoteAmountPrecision", "1"), "1")
    order_types = tuple(str(t) for t in raw.get("orderTypes", []))
    raw_status = str(raw.get("status", "1"))
    spot_allowed = bool(raw.get("isSpotTradingAllowed", True))
    status = "trading" if (raw_status == "1" and spot_allowed) else "halted"

    return SymbolOrderRules(
        symbol=display_symbol,
        mexc_symbol=mexc_symbol,
        base=base,
        quote=quote,
        price_precision=price_precision,
        qty_precision=qty_precision,
        min_qty=min_qty,
        min_notional=min_notional,
        order_types=order_types,
        status=status,
    )


def validate_order_params(
    rules: SymbolOrderRules,
    price: Decimal,
    qty: Decimal,
) -> tuple[bool, str | None, Decimal, Decimal]:
    """Validate and quantize order price and quantity against symbol rules."""
    if rules.status != "trading":
        return False, f"Symbol {rules.symbol} is halted", price, qty

    price_step = Decimal("10") ** (-rules.price_precision)
    qty_step = Decimal("10") ** (-rules.qty_precision)

    norm_price = price.quantize(price_step, rounding=ROUND_DOWN)
    norm_qty = qty.quantize(qty_step, rounding=ROUND_DOWN)

    if norm_price <= 0:
        return False, "Price must be greater than zero after precision rounding", norm_price, norm_qty
    if norm_qty < rules.min_qty:
        return (
            False,
            f"Quantity {norm_qty} is below minimum {rules.min_qty}",
            norm_price,
            norm_qty,
        )

    notional = norm_price * norm_qty
    if notional < rules.min_notional:
        return (
            False,
            f"Order notional {notional} is below minimum {rules.min_notional} {rules.quote}",
            norm_price,
            norm_qty,
        )

    return True, None, norm_price, norm_qty
