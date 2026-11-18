from __future__ import annotations

import calendar
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Candle, CandleCoverage, Symbol, utcnow
from exchanges.mexc.market_client import MexcMarketDataClient
from exchanges.mexc.order_rules import SymbolOrderRules, to_mexc_symbol

DEFAULT_SPOT_SYMBOLS: list[str] = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "DOT/USDT",
    "ARB/USDT",
    "SUI/USDT",
    "INJ/USDT",
    "RNDR/USDT",
    "DOGE/USDT",
]

TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1D": 86400,
    "3D": 259200,
    "1W": 604800,
    "1M": 2592000,
}

NATIVE_MEXC_INTERVALS: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "4h",
    "8h": "8h",
    "1D": "1d",
    "1W": "1W",
    "1M": "1M",
}

AGGREGATED_TIMEFRAMES: dict[str, tuple[str, int]] = {
    "3m": ("1m", 3),
    "2h": ("1h", 2),
    "6h": ("1h", 6),
    "12h": ("4h", 3),
    "3D": ("1D", 3),
}


def _normalize_utc_ts(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())


def bucket_open_time(ts_seconds: int, timeframe: str) -> int:
    """Align a UTC epoch timestamp (seconds) to the start of its timeframe bucket."""
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    if timeframe == "1W":
        dt = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)
        monday = (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(monday.timestamp())

    if timeframe == "1M":
        dt = datetime.fromtimestamp(ts_seconds, tz=timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return int(dt.timestamp())

    step = TIMEFRAME_SECONDS[timeframe]
    return (int(ts_seconds) // step) * step


def _expected_group_size(bucket_ts: int, target_timeframe: str) -> int | None:
    if target_timeframe in AGGREGATED_TIMEFRAMES:
        return AGGREGATED_TIMEFRAMES[target_timeframe][1]
    if target_timeframe == "1W":
        return 7
    if target_timeframe == "1M":
        dt = datetime.fromtimestamp(bucket_ts, tz=timezone.utc)
        return calendar.monthrange(dt.year, dt.month)[1]
    return None


def aggregate_candles(base_candles: list[dict[str, Any]], target_timeframe: str) -> list[dict[str, Any]]:
    """Aggregate lower-timeframe candles deterministically onto UTC timeframe boundaries."""
    if target_timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe: {target_timeframe}")
    if not base_candles:
        return []

    sorted_base = sorted(base_candles, key=lambda c: int(c["time"]))
    buckets: dict[int, list[dict[str, Any]]] = {}
    for row in sorted_base:
        b_time = bucket_open_time(int(row["time"]), target_timeframe)
        buckets.setdefault(b_time, []).append(row)

    aggregated: list[dict[str, Any]] = []
    for b_time in sorted(buckets.keys()):
        group = buckets[b_time]
        expected_count = _expected_group_size(b_time, target_timeframe)
        all_closed = all(bool(item.get("is_closed", True)) for item in group)
        is_complete = expected_count is None or len(group) == expected_count
        aggregated.append(
            {
                "time": b_time,
                "open": float(group[0]["open"]),
                "high": max(float(item["high"]) for item in group),
                "low": min(float(item["low"]) for item in group),
                "close": float(group[-1]["close"]),
                "volume": round(sum(float(item["volume"]) for item in group), 10),
                "is_closed": bool(all_closed and is_complete),
            }
        )
    return aggregated


@dataclass(frozen=True)
class DataQualityReport:
    """Validation metrics and snapshot fingerprint for an OHLCV series."""

    total_bars: int
    duplicate_count: int
    out_of_order_count: int
    invalid_ohlc_count: int
    gap_count: int
    is_clean: bool
    data_snapshot_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_candle_series(candles: list[dict[str, Any]], timeframe: str) -> DataQualityReport:
    """Check OHLCV series integrity, gaps, duplicates, ordering, and build snapshot hash."""
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    duplicate_count = 0
    out_of_order_count = 0
    invalid_ohlc_count = 0
    gap_count = 0

    seen_times: set[int] = set()
    prev_raw_time: int | None = None

    for c in candles:
        t = int(c["time"])
        o, h, l, cl, v = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"])
        if t in seen_times:
            duplicate_count += 1
        seen_times.add(t)

        if prev_raw_time is not None and t < prev_raw_time:
            out_of_order_count += 1
        prev_raw_time = t

        if o <= 0 or h < l or h < max(o, cl) or l > min(o, cl) or v < 0:
            invalid_ohlc_count += 1

    unique_times = sorted(seen_times)
    if len(unique_times) >= 2:
        if timeframe == "1M":
            for i in range(1, len(unique_times)):
                d_prev = datetime.fromtimestamp(unique_times[i - 1], tz=timezone.utc)
                d_curr = datetime.fromtimestamp(unique_times[i], tz=timezone.utc)
                month_diff = (d_curr.year - d_prev.year) * 12 + (d_curr.month - d_prev.month)
                if month_diff > 1:
                    gap_count += month_diff - 1
        else:
            step = TIMEFRAME_SECONDS[timeframe]
            for i in range(1, len(unique_times)):
                delta = unique_times[i] - unique_times[i - 1]
                if delta > step:
                    gap_count += (delta // step) - 1

    # Deterministic canonical hash of the ordered series
    ordered = sorted(candles, key=lambda c: int(c["time"]))
    lines = [
        f"{int(c['time'])}:{float(c['open']):.10f}:{float(c['high']):.10f}:{float(c['low']):.10f}:{float(c['close']):.10f}:{float(c['volume']):.10f}"
        for c in ordered
    ]
    snapshot_hash = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    is_clean = (
        duplicate_count == 0
        and out_of_order_count == 0
        and invalid_ohlc_count == 0
        and gap_count == 0
    )

    return DataQualityReport(
        total_bars=len(candles),
        duplicate_count=duplicate_count,
        out_of_order_count=out_of_order_count,
        invalid_ohlc_count=invalid_ohlc_count,
        gap_count=gap_count,
        is_clean=is_clean,
        data_snapshot_hash=snapshot_hash,
    )


def _upsert_symbol_rule(db: Session, rule: SymbolOrderRules) -> Symbol:
    row = db.execute(
        select(Symbol).where(Symbol.exchange == "mexc", Symbol.symbol == rule.symbol)
    ).scalar_one_or_none()
    if row is None:
        row = Symbol(
            exchange="mexc",
            symbol=rule.symbol,
            base=rule.base,
            quote=rule.quote,
            price_precision=rule.price_precision,
            qty_precision=rule.qty_precision,
            min_qty=rule.min_qty,
            min_notional=rule.min_notional,
            status=rule.status,
        )
        db.add(row)
        db.flush()
    else:
        row.price_precision = rule.price_precision
        row.qty_precision = rule.qty_precision
        row.min_qty = rule.min_qty
        row.min_notional = rule.min_notional
        row.status = rule.status
        row.updated_at = utcnow()
    return row


def ensure_symbol(db: Session, client: MexcMarketDataClient, symbol: str) -> Symbol:
    """Ensure a Spot pair exists in the symbols table, fetching rules from MEXC if absent."""
    clean = symbol.strip().upper()
    row = db.execute(select(Symbol).where(Symbol.exchange == "mexc", Symbol.symbol == clean)).scalar_one_or_none()
    if row is not None:
        return row

    rules = client.get_exchange_info([clean])
    if rules:
        return _upsert_symbol_rule(db, rules[0])

    if "/" in clean:
        base, quote = clean.split("/", 1)
    else:
        base, quote = clean.replace("USDT", ""), "USDT"
    fallback = SymbolOrderRules(
        symbol=clean,
        mexc_symbol=to_mexc_symbol(clean),
        base=base,
        quote=quote,
        price_precision=2,
        qty_precision=6,
        min_qty=Decimal("0.000001"),
        min_notional=Decimal("1"),
        order_types=("LIMIT", "MARKET", "LIMIT_MAKER"),
        status="trading",
    )
    return _upsert_symbol_rule(db, fallback)


def ensure_default_symbols(db: Session, client: MexcMarketDataClient) -> list[Symbol]:
    """Seed or refresh default Spot pairs from MEXC exchangeInfo."""
    rules = client.get_exchange_info(DEFAULT_SPOT_SYMBOLS)
    synced = [_upsert_symbol_rule(db, r) for r in rules]
    db.commit()
    return synced


def _fetch_paginated_klines(
    client: MexcMarketDataClient,
    symbol: str,
    mexc_interval: str,
    step_seconds: int,
    total_bars: int,
) -> list[dict[str, Any]]:
    """Fetch `total_bars` historical klines using backward endTime pagination."""
    collected: dict[int, dict[str, Any]] = {}
    end_ms: int | None = None
    remaining = max(1, total_bars)
    max_pages = 12

    for _ in range(max_pages):
        batch_limit = min(500, remaining)
        batch = client.get_klines(
            symbol,
            mexc_interval,
            end_time_ms=end_ms,
            limit=batch_limit,
        )
        if not batch:
            break

        prev_len = len(collected)
        for item in batch:
            collected[int(item["time"])] = item

        if len(collected) >= total_bars or len(batch) < batch_limit or len(collected) == prev_len:
            break

        earliest_sec = min(int(item["time"]) for item in batch)
        end_ms = (earliest_sec - step_seconds) * 1000
        remaining = total_bars - len(collected)

    ordered = [collected[t] for t in sorted(collected.keys())]
    return ordered[-total_bars:]


def _upsert_candles(
    db: Session,
    symbol_id: int,
    timeframe: str,
    candles: list[dict[str, Any]],
    source: str,
) -> None:
    if not candles:
        return
    min_dt = datetime.fromtimestamp(int(candles[0]["time"]), tz=timezone.utc)
    max_dt = datetime.fromtimestamp(int(candles[-1]["time"]), tz=timezone.utc)

    existing_rows = db.execute(
        select(Candle).where(
            Candle.symbol_id == symbol_id,
            Candle.timeframe == timeframe,
            Candle.open_time >= min_dt,
            Candle.open_time <= max_dt,
        )
    ).scalars().all()
    existing_by_ts = {_normalize_utc_ts(r.open_time): r for r in existing_rows}

    for item in candles:
        ts_sec = int(item["time"])
        open_dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
        existing = existing_by_ts.get(ts_sec)
        if existing is not None:
            existing.o = Decimal(str(item["open"]))
            existing.h = Decimal(str(item["high"]))
            existing.l = Decimal(str(item["low"]))
            existing.c = Decimal(str(item["close"]))
            existing.volume = Decimal(str(item["volume"]))
            existing.is_closed = bool(item.get("is_closed", True))
            existing.source = source
        else:
            db.add(
                Candle(
                    symbol_id=symbol_id,
                    timeframe=timeframe,
                    open_time=open_dt,
                    o=Decimal(str(item["open"])),
                    h=Decimal(str(item["high"])),
                    l=Decimal(str(item["low"])),
                    c=Decimal(str(item["close"])),
                    volume=Decimal(str(item["volume"])),
                    is_closed=bool(item.get("is_closed", True)),
                    source=source,
                )
            )


def _record_coverage(
    db: Session,
    symbol_id: int,
    timeframe: str,
    candles: list[dict[str, Any]],
    gap_count: int,
) -> None:
    if not candles:
        return
    from_dt = datetime.fromtimestamp(int(candles[0]["time"]), tz=timezone.utc)
    to_dt = datetime.fromtimestamp(int(candles[-1]["time"]), tz=timezone.utc)

    cov = db.execute(
        select(CandleCoverage).where(
            CandleCoverage.symbol_id == symbol_id,
            CandleCoverage.timeframe == timeframe,
        )
    ).scalar_one_or_none()
    if cov is None:
        db.add(
            CandleCoverage(
                symbol_id=symbol_id,
                timeframe=timeframe,
                from_ts=from_dt,
                to_ts=to_dt,
                validated_at=utcnow(),
                gap_count=gap_count,
            )
        )
    else:
        if _normalize_utc_ts(from_dt) < _normalize_utc_ts(cov.from_ts):
            cov.from_ts = from_dt
        if _normalize_utc_ts(to_dt) > _normalize_utc_ts(cov.to_ts):
            cov.to_ts = to_dt
        cov.validated_at = utcnow()
        cov.gap_count = gap_count


def sync_and_get_candles(
    db: Session,
    client: MexcMarketDataClient,
    symbol: str,
    timeframe: str,
    limit: int = 250,
) -> dict[str, Any]:
    """Fetch MEXC candles (native or aggregated), persist to DB, validate quality, and return series."""
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    clean_symbol = symbol.strip().upper()
    clamped_limit = max(10, min(limit, 1500))
    sym_row = ensure_symbol(db, client, clean_symbol)

    if timeframe in NATIVE_MEXC_INTERVALS:
        mexc_iv = NATIVE_MEXC_INTERVALS[timeframe]
        candles = _fetch_paginated_klines(
            client, clean_symbol, mexc_iv, TIMEFRAME_SECONDS[timeframe], clamped_limit
        )
        source = "mexc_native"
    else:
        base_tf, factor = AGGREGATED_TIMEFRAMES[timeframe]
        base_mexc_iv = NATIVE_MEXC_INTERVALS[base_tf]
        base_needed = min(5000, clamped_limit * factor + factor)
        base_candles = _fetch_paginated_klines(
            client, clean_symbol, base_mexc_iv, TIMEFRAME_SECONDS[base_tf], base_needed
        )
        candles = aggregate_candles(base_candles, timeframe)[-clamped_limit:]
        source = f"mexc_agg_{base_tf}"

    report = validate_candle_series(candles, timeframe)
    _upsert_candles(db, sym_row.id, timeframe, candles, source)
    _record_coverage(db, sym_row.id, timeframe, candles, report.gap_count)
    db.commit()

    return {
        "symbol": clean_symbol,
        "timeframe": timeframe,
        "source": source,
        "quality": report.to_dict(),
        "items": candles,
    }
