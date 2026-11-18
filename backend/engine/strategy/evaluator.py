from __future__ import annotations

import hashlib
import json
from typing import Any

from engine.indicators.catalog import INDICATOR_SPECS, validate_and_coerce_params
from engine.indicators.compute import compute_indicator

_VALID_OPS = {">", ">=", "<", "<=", "=="}
_VALID_NODE_TYPES = {"AND", "OR", "NOT", "COMPARE", "CROSS_ABOVE", "CROSS_BELOW"}


def compute_definition_hash(definition: dict[str, Any]) -> str:
    """Return deterministic SHA-256 digest of a canonical strategy definition."""
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_rule_node(node: dict[str, Any], valid_refs: set[str]) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValueError("Rule node must be an object")
    node_type = str(node.get("type", "")).upper()
    if node_type not in _VALID_NODE_TYPES:
        raise ValueError(f"Unsupported rule node type '{node_type}'")

    if node_type in {"AND", "OR"}:
        children = node.get("children")
        if not isinstance(children, list) or len(children) == 0:
            raise ValueError(f"{node_type} node requires a non-empty children list")
        return {
            "type": node_type,
            "children": [_validate_rule_node(c, valid_refs) for c in children],
        }

    if node_type == "NOT":
        child = node.get("child")
        if not isinstance(child, dict):
            raise ValueError("NOT node requires a 'child' rule object")
        return {"type": "NOT", "child": _validate_rule_node(child, valid_refs)}

    left = str(node.get("left", "")).strip()
    if not left:
        raise ValueError(f"{node_type} node requires 'left' operand")
    _check_operand(left, valid_refs)

    right_raw = node.get("right")
    if right_raw is None:
        raise ValueError(f"{node_type} node requires 'right' operand")
    if isinstance(right_raw, str):
        _check_operand(right_raw.strip(), valid_refs)
        right: str | float = right_raw.strip()
    else:
        right = float(right_raw)

    if node_type == "COMPARE":
        op = str(node.get("op", ">")).strip()
        if op not in _VALID_OPS:
            raise ValueError(f"Unsupported comparison operator '{op}'")
        return {"type": "COMPARE", "left": left, "op": op, "right": right}

    return {"type": node_type, "left": left, "right": right}


def _check_operand(ref: str, valid_refs: set[str]) -> None:
    if ref.startswith("price."):
        if ref not in {"price.open", "price.high", "price.low", "price.close", "price.volume"}:
            raise ValueError(f"Unknown price operand '{ref}'")
        return
    if ref not in valid_refs:
        raise ValueError(f"Rule references unknown indicator series '{ref}'")


def validate_strategy_definition(raw_defn: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a complete StrategyDefinition (supports 6+ indicators and rule trees)."""
    if not isinstance(raw_defn, dict):
        raise ValueError("Strategy definition must be an object")

    indicators_raw = raw_defn.get("indicators", [])
    if not isinstance(indicators_raw, list) or len(indicators_raw) == 0:
        raise ValueError("Strategy requires at least one indicator")

    seen_keys: set[str] = set()
    valid_refs: set[str] = set()
    normalized_indicators: list[dict[str, Any]] = []

    for item in indicators_raw:
        if not isinstance(item, dict):
            raise ValueError("Each indicator entry must be an object")
        key = str(item.get("key", "")).strip()
        ind_id = str(item.get("indicator_id", "")).strip()
        if not key:
            raise ValueError("Indicator instance requires a non-empty 'key'")
        if key in seen_keys:
            raise ValueError(f"Duplicate indicator key '{key}'")
        if ind_id not in INDICATOR_SPECS:
            raise ValueError(f"Unknown indicator_id '{ind_id}'")
        seen_keys.add(key)

        params = validate_and_coerce_params(ind_id, item.get("params"))
        spec = INDICATOR_SPECS[ind_id]
        for out in spec.outputs:
            valid_refs.add(f"{key}.{out.key}")

        tf_val = item.get("timeframe")
        normalized_indicators.append(
            {
                "key": key,
                "indicator_id": ind_id,
                "params": params,
                "timeframe": str(tf_val).strip() if tf_val else None,
                "weight": float(item.get("weight", 1.0)),
                "enabled": bool(item.get("enabled", True)),
            }
        )

    entry_rule_raw = raw_defn.get("entry_rule")
    exit_rule_raw = raw_defn.get("exit_rule")
    if not isinstance(entry_rule_raw, dict):
        raise ValueError("Strategy requires an 'entry_rule' object")
    if not isinstance(exit_rule_raw, dict):
        raise ValueError("Strategy requires an 'exit_rule' object")

    entry_rule = _validate_rule_node(entry_rule_raw, valid_refs)
    exit_rule = _validate_rule_node(exit_rule_raw, valid_refs)

    sl_pct = float(raw_defn.get("stop_loss_pct", 2.0))
    tp_pct = float(raw_defn.get("take_profit_pct", 4.0))
    if sl_pct <= 0 or sl_pct > 95:
        raise ValueError("stop_loss_pct must be between 0 and 95")
    if tp_pct <= 0 or tp_pct > 500:
        raise ValueError("take_profit_pct must be between 0 and 500")

    signal_mode = str(raw_defn.get("signal_mode", "closed_candle"))
    if signal_mode not in {"closed_candle", "intrabar"}:
        raise ValueError("signal_mode must be 'closed_candle' or 'intrabar'")

    return {
        "symbol": str(raw_defn.get("symbol", "BTC/USDT")).strip().upper(),
        "timeframe": str(raw_defn.get("timeframe", "15m")).strip(),
        "signal_mode": signal_mode,
        "stop_loss_pct": round(sl_pct, 4),
        "take_profit_pct": round(tp_pct, 4),
        "indicators": normalized_indicators,
        "entry_rule": entry_rule,
        "exit_rule": exit_rule,
    }


def _align_htf_series_causally(
    base_times: list[int],
    base_step_sec: int,
    htf_points: list[dict[str, Any]],
    htf_step_sec: int,
) -> list[float | None]:
    """Align higher-timeframe values onto base bars using ONLY HTF bars already closed."""
    out: list[float | None] = [None] * len(base_times)
    if not htf_points:
        return out

    j = 0
    latest_val: float | None = None
    for i, bt in enumerate(base_times):
        base_close_ts = bt + base_step_sec
        while j < len(htf_points) and (int(htf_points[j]["time"]) + htf_step_sec) <= base_close_ts:
            latest_val = float(htf_points[j]["value"])
            j += 1
        out[i] = latest_val
    return out


def _eval_rule_at(
    node: dict[str, Any],
    idx: int,
    series_map: dict[str, list[float | None]],
) -> bool:
    ntype = node["type"]
    if ntype == "AND":
        return all(_eval_rule_at(c, idx, series_map) for c in node["children"])
    if ntype == "OR":
        return any(_eval_rule_at(c, idx, series_map) for c in node["children"])
    if ntype == "NOT":
        return not _eval_rule_at(node["child"], idx, series_map)

    def _val(operand: str | float, bar_idx: int) -> float | None:
        if isinstance(operand, (int, float)):
            return float(operand)
        arr = series_map.get(operand)
        if not arr or bar_idx < 0 or bar_idx >= len(arr):
            return None
        return arr[bar_idx]

    l_curr = _val(node["left"], idx)
    r_curr = _val(node["right"], idx)
    if l_curr is None or r_curr is None:
        return False

    if ntype == "COMPARE":
        op = node["op"]
        if op == ">":
            return l_curr > r_curr
        if op == ">=":
            return l_curr >= r_curr
        if op == "<":
            return l_curr < r_curr
        if op == "<=":
            return l_curr <= r_curr
        return l_curr == r_curr

    if idx == 0:
        return False
    l_prev = _val(node["left"], idx - 1)
    r_prev = _val(node["right"], idx - 1)
    if l_prev is None or r_prev is None:
        return False

    if ntype == "CROSS_ABOVE":
        return l_prev <= r_prev and l_curr > r_curr
    if ntype == "CROSS_BELOW":
        return l_prev >= r_prev and l_curr < r_curr
    return False


def evaluate_strategy(
    raw_defn: dict[str, Any],
    candles: list[dict[str, Any]],
    htf_candles: dict[str, tuple[int, list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    """Evaluate a multi-indicator strategy causally over OHLCV candles."""
    defn = validate_strategy_definition(raw_defn)
    n = len(candles)
    if n == 0:
        return {
            "definition": defn,
            "entry_signals": [],
            "exit_signals": [],
            "confluence_scores": [],
            "series": {},
        }

    base_times = [int(c["time"]) for c in candles]
    base_step = (base_times[1] - base_times[0]) if n >= 2 else 900
    time_to_idx = {t: i for i, t in enumerate(base_times)}

    series_map: dict[str, list[float | None]] = {
        "price.open": [float(c["open"]) for c in candles],
        "price.high": [float(c["high"]) for c in candles],
        "price.low": [float(c["low"]) for c in candles],
        "price.close": [float(c["close"]) for c in candles],
        "price.volume": [float(c["volume"]) for c in candles],
    }

    for inst in defn["indicators"]:
        if not inst["enabled"]:
            continue
        tf_override = inst.get("timeframe")
        if tf_override and htf_candles and tf_override in htf_candles:
            htf_step, htf_bars = htf_candles[tf_override]
            computed = compute_indicator(inst["indicator_id"], htf_bars, inst["params"])
            for out_key, pts in computed.items():
                series_map[f"{inst['key']}.{out_key}"] = _align_htf_series_causally(
                    base_times, base_step, pts, htf_step
                )
        else:
            computed = compute_indicator(inst["indicator_id"], candles, inst["params"])
            for out_key, pts in computed.items():
                arr: list[float | None] = [None] * n
                for pt in pts:
                    idx = time_to_idx.get(int(pt["time"]))
                    if idx is not None:
                        arr[idx] = float(pt["value"])
                series_map[f"{inst['key']}.{out_key}"] = arr

    entry_signals: list[bool] = [False] * n
    exit_signals: list[bool] = [False] * n
    confluence_scores: list[float] = [0.0] * n

    entry_rule = defn["entry_rule"]
    exit_rule = defn["exit_rule"]
    top_children = entry_rule.get("children") if entry_rule["type"] in {"AND", "OR"} else [entry_rule]

    for i in range(n):
        entry_signals[i] = _eval_rule_at(entry_rule, i, series_map)
        exit_signals[i] = _eval_rule_at(exit_rule, i, series_map)
        if top_children:
            passed = sum(1 for ch in top_children if _eval_rule_at(ch, i, series_map))
            confluence_scores[i] = round(passed / len(top_children), 4)

    return {
        "definition": defn,
        "entry_signals": entry_signals,
        "exit_signals": exit_signals,
        "confluence_scores": confluence_scores,
        "series": series_map,
    }
