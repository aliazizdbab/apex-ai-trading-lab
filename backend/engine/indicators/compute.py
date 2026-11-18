from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from engine.indicators.catalog import validate_and_coerce_params


def compute_heikin_ashi(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform standard OHLCV candles into causal Heikin Ashi candles."""
    if not candles:
        return []

    out: list[dict[str, Any]] = []
    prev_ha_open: float | None = None
    prev_ha_close: float | None = None

    for c in candles:
        o = float(c["open"])
        h = float(c["high"])
        l = float(c["low"])
        cl = float(c["close"])

        ha_close = (o + h + l + cl) / 4.0
        if prev_ha_open is None or prev_ha_close is None:
            ha_open = (o + cl) / 2.0
        else:
            ha_open = (prev_ha_open + prev_ha_close) / 2.0

        ha_high = max(h, ha_open, ha_close)
        ha_low = min(l, ha_open, ha_close)

        row: dict[str, Any] = {
            "time": int(c["time"]),
            "open": round(ha_open, 10),
            "high": round(ha_high, 10),
            "low": round(ha_low, 10),
            "close": round(ha_close, 10),
            "volume": float(c["volume"]),
        }
        if "is_closed" in c:
            row["is_closed"] = bool(c["is_closed"])
        out.append(row)
        prev_ha_open = ha_open
        prev_ha_close = ha_close

    return out


def _extract_source(candles: list[dict[str, Any]], source: str) -> list[float]:
    if source == "open":
        return [float(c["open"]) for c in candles]
    if source == "high":
        return [float(c["high"]) for c in candles]
    if source == "low":
        return [float(c["low"]) for c in candles]
    if source == "hl2":
        return [(float(c["high"]) + float(c["low"])) / 2.0 for c in candles]
    if source == "hlc3":
        return [(float(c["high"]) + float(c["low"]) + float(c["close"])) / 3.0 for c in candles]
    if source == "ohlc4":
        return [(float(c["open"]) + float(c["high"]) + float(c["low"]) + float(c["close"])) / 4.0 for c in candles]
    return [float(c["close"]) for c in candles]


def _sma_array(values: list[float | None], length: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if length <= 0 or n < length:
        return out

    for i in range(length - 1, n):
        window = values[i - length + 1 : i + 1]
        if any(v is None for v in window):
            continue
        out[i] = sum(float(v) for v in window if v is not None) / length
    return out


def _ema_array(values: list[float | None], length: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if length <= 0 or n == 0:
        return out

    alpha = 2.0 / (length + 1.0)
    # Find contiguous valid prefix to seed EMA with SMA of first `length` valid points
    valid_run: list[float] = []
    ema_val: float | None = None

    for i, val in enumerate(values):
        if val is None:
            valid_run.clear()
            ema_val = None
            continue
        fval = float(val)
        if ema_val is None:
            valid_run.append(fval)
            if len(valid_run) == length:
                ema_val = sum(valid_run) / length
                out[i] = ema_val
        else:
            ema_val = alpha * fval + (1.0 - alpha) * ema_val
            out[i] = ema_val
    return out


def _rma_array(values: list[float | None], length: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if length <= 0 or n == 0:
        return out

    seed: list[float] = []
    rma_val: float | None = None
    for i, val in enumerate(values):
        if val is None:
            seed.clear()
            rma_val = None
            continue
        fval = float(val)
        if rma_val is None:
            seed.append(fval)
            if len(seed) == length:
                rma_val = sum(seed) / length
                out[i] = rma_val
        else:
            rma_val = (rma_val * (length - 1) + fval) / length
            out[i] = rma_val
    return out


def _shift_forward(values: list[float | None], offset: int) -> list[float | None]:
    if offset <= 0:
        return values
    n = len(values)
    out: list[float | None] = [None] * n
    for i in range(offset, n):
        out[i] = values[i - offset]
    return out


def _true_range(candles: list[dict[str, Any]]) -> list[float]:
    tr: list[float] = []
    for i, c in enumerate(candles):
        h = float(c["high"])
        l = float(c["low"])
        if i == 0:
            tr.append(h - l)
        else:
            prev_c = float(candles[i - 1]["close"])
            tr.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return tr


def _to_points(candles: list[dict[str, Any]], values: list[float | None]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for c, val in zip(candles, values):
        if val is not None and math.isfinite(val):
            points.append({"time": int(c["time"]), "value": round(float(val), 8)})
    return points


def _anchor_key(ts_seconds: int, anchor: str) -> tuple[int, int, int]:
    dt = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)
    if anchor == "week":
        monday = (dt - timedelta(days=dt.weekday())).date()
        return (monday.year, monday.month, monday.day)
    if anchor == "month":
        return (dt.year, dt.month, 1)
    return (dt.year, dt.month, dt.day)


def compute_indicator(
    indicator_id: str,
    candles: list[dict[str, Any]],
    raw_params: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Compute a built-in causal technical indicator over OHLCV candles."""
    params = validate_and_coerce_params(indicator_id, raw_params)
    n = len(candles)
    if n == 0:
        return {}

    if indicator_id == "sma":
        src = _extract_source(candles, params["source"])
        vals = _shift_forward(_sma_array(list(src), params["length"]), params["offset"])
        return {"sma": _to_points(candles, vals)}

    if indicator_id == "ema":
        src = _extract_source(candles, params["source"])
        vals = _shift_forward(_ema_array(list(src), params["length"]), params["offset"])
        return {"ema": _to_points(candles, vals)}

    if indicator_id == "bb":
        length = params["length"]
        mult = params["mult"]
        src = _extract_source(candles, params["source"])
        basis = _sma_array(list(src), length)
        upper: list[float | None] = [None] * n
        lower: list[float | None] = [None] * n
        for i in range(length - 1, n):
            b = basis[i]
            if b is None:
                continue
            win = src[i - length + 1 : i + 1]
            var = sum((x - b) ** 2 for x in win) / length
            sd = math.sqrt(max(0.0, var))
            upper[i] = b + mult * sd
            lower[i] = b - mult * sd
        return {
            "upper": _to_points(candles, upper),
            "basis": _to_points(candles, basis),
            "lower": _to_points(candles, lower),
        }

    if indicator_id == "vwap":
        anchor = params["anchor"]
        src = _extract_source(candles, params["source"])
        vwap_vals: list[float | None] = [None] * n
        prev_key: tuple[int, int, int] | None = None
        cum_pv = 0.0
        cum_v = 0.0
        for i, c in enumerate(candles):
            key = _anchor_key(int(c["time"]), anchor)
            if key != prev_key:
                cum_pv = 0.0
                cum_v = 0.0
                prev_key = key
            vol = max(0.0, float(c["volume"]))
            cum_pv += src[i] * vol
            cum_v += vol
            vwap_vals[i] = (cum_pv / cum_v) if cum_v > 0 else src[i]
        return {"vwap": _to_points(candles, vwap_vals)}

    if indicator_id == "atr":
        tr = _true_range(candles)
        atr_vals = _rma_array(list(tr), params["length"])
        return {"atr": _to_points(candles, atr_vals)}

    if indicator_id == "supertrend":
        atr_len = params["atr_length"]
        factor = params["factor"]
        atr_vals = _rma_array(list(_true_range(candles)), atr_len)
        st_vals: list[float | None] = [None] * n

        prev_fu: float | None = None
        prev_fl: float | None = None
        prev_dir = 1

        for i, c in enumerate(candles):
            atr = atr_vals[i]
            if atr is None:
                continue
            hl2 = (float(c["high"]) + float(c["low"])) / 2.0
            bu = hl2 + factor * atr
            bl = hl2 - factor * atr
            close_px = float(c["close"])

            if prev_fu is None or prev_fl is None:
                fu = bu
                fl = bl
                direction = 1 if close_px >= fu else -1
            else:
                prev_close = float(candles[i - 1]["close"])
                fu = bu if (bu < prev_fu or prev_close > prev_fu) else prev_fu
                fl = bl if (bl > prev_fl or prev_close < prev_fl) else prev_fl
                if prev_dir == -1 and close_px > fu:
                    direction = 1
                elif prev_dir == 1 and close_px < fl:
                    direction = -1
                else:
                    direction = prev_dir

            st_vals[i] = fl if direction == 1 else fu
            prev_fu = fu
            prev_fl = fl
            prev_dir = direction

        return {"supertrend": _to_points(candles, st_vals)}

    if indicator_id == "ichimoku":
        conv_p = params["conversion_periods"]
        base_p = params["base_periods"]
        span2_p = params["lagging_span2_periods"]
        disp = params["displacement"]

        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]

        def _mid_range(period: int) -> list[float | None]:
            res: list[float | None] = [None] * n
            for i in range(period - 1, n):
                hh = max(highs[i - period + 1 : i + 1])
                ll = min(lows[i - period + 1 : i + 1])
                res[i] = (hh + ll) / 2.0
            return res

        tenkan = _mid_range(conv_p)
        kijun = _mid_range(base_p)
        raw_span_a: list[float | None] = [
            ((t + k) / 2.0) if (t is not None and k is not None) else None
            for t, k in zip(tenkan, kijun)
        ]
        raw_span_b = _mid_range(span2_p)

        shift = max(0, disp - 1)
        senkou_a = _shift_forward(raw_span_a, shift)
        senkou_b = _shift_forward(raw_span_b, shift)

        return {
            "tenkan": _to_points(candles, tenkan),
            "kijun": _to_points(candles, kijun),
            "senkou_a": _to_points(candles, senkou_a),
            "senkou_b": _to_points(candles, senkou_b),
        }

    if indicator_id == "rsi":
        length = params["length"]
        src = _extract_source(candles, params["source"])
        gains: list[float | None] = [None] * n
        losses: list[float | None] = [None] * n
        for i in range(1, n):
            diff = src[i] - src[i - 1]
            gains[i] = max(diff, 0.0)
            losses[i] = max(-diff, 0.0)

        avg_g = _rma_array(gains, length)
        avg_l = _rma_array(losses, length)
        rsi_vals: list[float | None] = [None] * n
        for i in range(n):
            g = avg_g[i]
            l = avg_l[i]
            if g is None or l is None:
                continue
            if l == 0.0:
                rsi_vals[i] = 100.0 if g > 0.0 else 50.0
            else:
                rs = g / l
                rsi_vals[i] = 100.0 - (100.0 / (1.0 + rs))
        return {"rsi": _to_points(candles, rsi_vals)}

    if indicator_id == "macd":
        src = _extract_source(candles, params["source"])
        fast = _ema_array(list(src), params["fast_length"])
        slow = _ema_array(list(src), params["slow_length"])
        macd_line: list[float | None] = [
            (f - s) if (f is not None and s is not None) else None for f, s in zip(fast, slow)
        ]
        signal_line = _ema_array(macd_line, params["signal_length"])
        hist: list[float | None] = [
            (m - sig) if (m is not None and sig is not None) else None
            for m, sig in zip(macd_line, signal_line)
        ]
        return {
            "macd": _to_points(candles, macd_line),
            "signal": _to_points(candles, signal_line),
            "histogram": _to_points(candles, hist),
        }

    if indicator_id == "adx":
        di_len = params["di_length"]
        adx_smooth = params["adx_smoothing"]
        tr = _true_range(candles)
        tr_valid: list[float | None] = [None] + [float(x) for x in tr[1:]]
        plus_dm: list[float | None] = [None] * n
        minus_dm: list[float | None] = [None] * n

        for i in range(1, n):
            up = float(candles[i]["high"]) - float(candles[i - 1]["high"])
            down = float(candles[i - 1]["low"]) - float(candles[i]["low"])
            plus_dm[i] = up if (up > down and up > 0.0) else 0.0
            minus_dm[i] = down if (down > up and down > 0.0) else 0.0

        tr_rma = _rma_array(tr_valid, di_len)
        pdm_rma = _rma_array(plus_dm, di_len)
        mdm_rma = _rma_array(minus_dm, di_len)

        plus_di: list[float | None] = [None] * n
        minus_di: list[float | None] = [None] * n
        dx: list[float | None] = [None] * n

        for i in range(n):
            t_r = tr_rma[i]
            p_r = pdm_rma[i]
            m_r = mdm_rma[i]
            if t_r is None or p_r is None or m_r is None:
                continue
            pdi = (100.0 * p_r / t_r) if t_r > 0.0 else 0.0
            mdi = (100.0 * m_r / t_r) if t_r > 0.0 else 0.0
            plus_di[i] = pdi
            minus_di[i] = mdi
            denom = pdi + mdi
            dx[i] = (100.0 * abs(pdi - mdi) / denom) if denom > 0.0 else 0.0

        adx_vals = _rma_array(dx, adx_smooth)
        return {
            "adx": _to_points(candles, adx_vals),
            "plus_di": _to_points(candles, plus_di),
            "minus_di": _to_points(candles, minus_di),
        }

    if indicator_id == "stoch":
        k_len = params["k_length"]
        k_smooth = params["k_smoothing"]
        d_len = params["d_length"]

        raw_k: list[float | None] = [None] * n
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        for i in range(k_len - 1, n):
            hh = max(highs[i - k_len + 1 : i + 1])
            ll = min(lows[i - k_len + 1 : i + 1])
            denom = hh - ll
            raw_k[i] = (100.0 * (float(candles[i]["close"]) - ll) / denom) if denom > 0.0 else 50.0

        k_vals = _sma_array(raw_k, k_smooth)
        d_vals = _sma_array(k_vals, d_len)
        return {
            "k": _to_points(candles, k_vals),
            "d": _to_points(candles, d_vals),
        }

    raise ValueError(f"Unsupported indicator '{indicator_id}'")
