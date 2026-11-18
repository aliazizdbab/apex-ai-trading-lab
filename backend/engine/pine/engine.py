from __future__ import annotations

import hashlib
import re
from typing import Any

from engine.indicators.compute import compute_indicator

_UNSUPPORTED_CALLS = (
    "line.new",
    "label.new",
    "box.new",
    "table.new",
    "polyline.new",
    "array.new",
    "matrix.new",
)

_SUPPORTED_TA = (
    "ta.sma",
    "ta.ema",
    "ta.rsi",
    "ta.macd",
    "ta.bb",
    "ta.atr",
    "ta.supertrend",
    "ta.crossover",
    "ta.crossunder",
)

_HEADER_RE = re.compile(r"^\s*(indicator|strategy)\s*\(\s*[\"']([^\"']+)[\"']")
_VERSION_RE = re.compile(r"//@version=(\d+)")
_INPUT_RE = re.compile(
    r"^\s*([A-Za-z_]\w*)\s*=\s*input\.(int|float|string|bool)\s*\((.*)\)\s*$"
)
_TUPLE_ASSIGN_RE = re.compile(r"^\s*\[([^\]]+)\]\s*=\s*(.+)$")
_SIMPLE_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+)$")
_PLOT_RE = re.compile(r"^\s*plot\s*\((.*)\)\s*$")
_STRATEGY_ENTRY_RE = re.compile(r"^\s*strategy\.entry\s*\((.*)\)\s*$")
_STRATEGY_CLOSE_RE = re.compile(r"^\s*strategy\.(?:close|exit)\s*\((.*)\)\s*$")
_ALERT_RE = re.compile(r"^\s*alertcondition\s*\((.*)\)\s*$")
_IF_RE = re.compile(r"^\s*if\s+(.+)$")


def _split_args(arg_str: str) -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    in_quote: str | None = None
    for ch in arg_str:
        if in_quote:
            cur.append(ch)
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ("'", '"'):
            in_quote = ch
            cur.append(ch)
        elif ch in ("(", "["):
            depth += 1
            cur.append(ch)
        elif ch in (")", "]"):
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur.clear()
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return [p for p in parts if p]


def _strip_comments(line: str) -> str:
    in_quote: str | None = None
    for idx, ch in enumerate(line):
        if in_quote:
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ("'", '"'):
            in_quote = ch
        elif ch == "/" and idx + 1 < len(line) and line[idx + 1] == "/":
            return line[:idx]
    return line


def _parse_literal(raw: str) -> Any:
    val = raw.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    if val == "true":
        return True
    if val == "false":
        return False
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        return val


def analyze_pine_script(source: str) -> dict[str, Any]:
    """Lex, parse AST, extract dynamic inputs, and inspect Pine compatibility & repainting."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Pine source code cannot be empty")

    lines = source.splitlines()
    pine_version = 5
    script_type = "indicator"
    title = "Untitled Pine Script"

    inputs: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []
    builtin_calls: set[str] = set()
    unsupported_features: list[str] = []
    repaint_warnings: list[str] = []
    alerts: list[str] = []
    referenced_timeframes: set[str] = set()

    if "lookahead_on" in source:
        repaint_warnings.append("barmerge.lookahead_on detected: future bar values can cause historical repainting.")
    if "barstate.isrealtime" in source or "barstate.islast" in source:
        repaint_warnings.append("barstate.isrealtime/islast detected: behavior differs between live intrabar and closed history.")

    for call in _UNSUPPORTED_CALLS:
        if call in source:
            unsupported_features.append(f"Unsupported drawing/collection call '{call}'")

    if "request.security" in source:
        builtin_calls.add("request.security")
        for m in re.finditer(r"request\.security\s*\([^,]+,\s*[\"']([^\"']+)[\"']", source):
            referenced_timeframes.add(m.group(1))

    active_if_cond: str | None = None
    active_if_indent = 0

    for line_no, raw_line in enumerate(lines, start=1):
        ver_m = _VERSION_RE.search(raw_line)
        if ver_m:
            pine_version = int(ver_m.group(1))
            continue

        clean = _strip_comments(raw_line).rstrip()
        if not clean.strip():
            continue

        indent = len(clean) - len(clean.lstrip(" \t"))
        if active_if_cond is not None and indent <= active_if_indent:
            active_if_cond = None

        hdr = _HEADER_RE.match(clean)
        if hdr:
            script_type = hdr.group(1)
            title = hdr.group(2)
            continue

        for ta_fn in _SUPPORTED_TA:
            if ta_fn in clean:
                builtin_calls.add(ta_fn)

        inp_m = _INPUT_RE.match(clean)
        if inp_m:
            var_name, inp_type, args_raw = inp_m.groups()
            args = _split_args(args_raw)
            default_val = _parse_literal(args[0]) if args else (0 if inp_type == "int" else 0.0)
            inp_title = var_name
            min_v: float | None = None
            max_v: float | None = None
            for a in args[1:]:
                if "=" in a:
                    k, v = [x.strip() for x in a.split("=", 1)]
                    if k == "title":
                        inp_title = str(_parse_literal(v))
                    elif k == "minval":
                        min_v = float(_parse_literal(v))
                    elif k == "maxval":
                        max_v = float(_parse_literal(v))
                elif isinstance(_parse_literal(a), str) and inp_title == var_name:
                    inp_title = str(_parse_literal(a))
            inputs.append(
                {
                    "name": var_name,
                    "type": inp_type,
                    "default": default_val,
                    "title": inp_title,
                    "minval": min_v,
                    "maxval": max_v,
                }
            )
            statements.append({"kind": "input", "line": line_no, "name": var_name, "default": default_val})
            continue

        if_m = _IF_RE.match(clean)
        if if_m:
            active_if_cond = if_m.group(1).strip()
            active_if_indent = indent
            continue

        plot_m = _PLOT_RE.match(clean)
        if plot_m:
            args = _split_args(plot_m.group(1))
            expr = args[0] if args else "close"
            p_title = expr
            for a in args[1:]:
                if "=" in a:
                    k, v = [x.strip() for x in a.split("=", 1)]
                    if k == "title":
                        p_title = str(_parse_literal(v))
            statements.append({"kind": "plot", "line": line_no, "expr": expr, "title": p_title})
            continue

        ent_m = _STRATEGY_ENTRY_RE.match(clean)
        if ent_m:
            script_type = "strategy"
            args = _split_args(ent_m.group(1))
            cond = active_if_cond
            for a in args:
                if a.startswith("when="):
                    cond = a.split("=", 1)[1].strip()
            statements.append({"kind": "strategy_entry", "line": line_no, "when": cond})
            continue

        cls_m = _STRATEGY_CLOSE_RE.match(clean)
        if cls_m:
            script_type = "strategy"
            args = _split_args(cls_m.group(1))
            cond = active_if_cond
            for a in args:
                if a.startswith("when="):
                    cond = a.split("=", 1)[1].strip()
            statements.append({"kind": "strategy_exit", "line": line_no, "when": cond})
            continue

        al_m = _ALERT_RE.match(clean)
        if al_m:
            alerts.append(al_m.group(1).strip())
            continue

        tup_m = _TUPLE_ASSIGN_RE.match(clean)
        if tup_m:
            targets = [t.strip() for t in tup_m.group(1).split(",")]
            expr = tup_m.group(2).strip()
            statements.append({"kind": "tuple_assign", "line": line_no, "targets": targets, "expr": expr})
            continue

        sim_m = _SIMPLE_ASSIGN_RE.match(clean)
        if sim_m:
            target = sim_m.group(1).strip()
            expr = sim_m.group(2).strip()
            statements.append({"kind": "assign", "line": line_no, "target": target, "expr": expr})
            continue

    sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
    supported = len(unsupported_features) == 0

    return {
        "title": title,
        "pine_version": pine_version,
        "script_type": script_type,
        "sha256": sha,
        "inputs": inputs,
        "builtin_indicators": sorted(builtin_calls),
        "referenced_timeframes": sorted(referenced_timeframes),
        "alerts": alerts,
        "ast": {"statement_count": len(statements), "statements": statements},
        "compat_report": {
            "supported": supported,
            "unsupported_features": unsupported_features,
            "repaint_warnings": repaint_warnings,
            "sandbox_mode": "ast_tree_walking_no_eval",
        },
    }


def _resolve_scalar(expr: str, env: dict[str, Any]) -> Any:
    e = expr.strip()
    if e in env and not isinstance(env[e], list):
        return env[e]
    return _parse_literal(e)


def _resolve_series(expr: str, candles: list[dict[str, Any]], env: dict[str, Any]) -> list[float | None]:
    e = expr.strip()
    n = len(candles)
    if e in env:
        val = env[e]
        if isinstance(val, list):
            return val
        return [float(val)] * n

    if e in {"close", "open", "high", "low", "volume"}:
        return [float(c[e]) for c in candles]
    if e == "hl2":
        return [(float(c["high"]) + float(c["low"])) / 2.0 for c in candles]
    if e == "hlc3":
        return [(float(c["high"]) + float(c["low"]) + float(c["close"])) / 3.0 for c in candles]

    lit = _parse_literal(e)
    if isinstance(lit, (int, float)):
        return [float(lit)] * n

    # Binary arithmetic (e.g. close + 10)
    for op in ("+", "-", "*", "/"):
        if op in e and "(" not in e:
            left_s, right_s = [p.strip() for p in e.split(op, 1)]
            ls = _resolve_series(left_s, candles, env)
            rs = _resolve_series(right_s, candles, env)
            out: list[float | None] = []
            for a, b in zip(ls, rs):
                if a is None or b is None:
                    out.append(None)
                elif op == "+":
                    out.append(a + b)
                elif op == "-":
                    out.append(a - b)
                elif op == "*":
                    out.append(a * b)
                elif op == "/":
                    out.append(a / b if abs(b) > 1e-12 else None)
            return out

    raise ValueError(f"Unsupported Pine expression '{expr}'")


def _eval_ta_call(
    expr: str,
    candles: list[dict[str, Any]],
    env: dict[str, Any],
) -> dict[str, list[float | None]]:
    m = re.match(r"^(ta\.[a-z_]+)\s*\((.*)\)\s*$", expr.strip())
    if not m:
        raise ValueError(f"Unsupported Pine call '{expr}'")
    fn = m.group(1)
    args = _split_args(m.group(2))
    n = len(candles)
    time_to_idx = {int(c["time"]): i for i, c in enumerate(candles)}

    def _align_points(pts: list[dict[str, Any]]) -> list[float | None]:
        arr: list[float | None] = [None] * n
        for pt in pts:
            idx = time_to_idx.get(int(pt["time"]))
            if idx is not None:
                arr[idx] = float(pt["value"])
        return arr

    if fn in {"ta.sma", "ta.ema", "ta.rsi"}:
        src_name = args[0].strip() if len(args) >= 1 else "close"
        length = int(_resolve_scalar(args[1], env)) if len(args) >= 2 else 14
        src_key = src_name if src_name in {"open", "high", "low", "close", "hl2", "hlc3"} else "close"
        ind_id = fn.split(".")[1]
        res = compute_indicator(ind_id, candles, {"length": length, "source": src_key})
        return {"_single": _align_points(res[ind_id])}

    if fn == "ta.atr":
        length = int(_resolve_scalar(args[0], env)) if args else 14
        res = compute_indicator("atr", candles, {"length": length})
        return {"_single": _align_points(res["atr"])}

    if fn == "ta.macd":
        src_name = args[0].strip() if len(args) >= 1 else "close"
        fast = int(_resolve_scalar(args[1], env)) if len(args) >= 2 else 12
        slow = int(_resolve_scalar(args[2], env)) if len(args) >= 3 else 26
        sig = int(_resolve_scalar(args[3], env)) if len(args) >= 4 else 9
        src_key = src_name if src_name in {"open", "high", "low", "close", "hl2", "hlc3"} else "close"
        res = compute_indicator(
            "macd", candles, {"fast_length": fast, "slow_length": slow, "signal_length": sig, "source": src_key}
        )
        return {
            "macd": _align_points(res["macd"]),
            "signal": _align_points(res["signal"]),
            "histogram": _align_points(res["histogram"]),
        }

    if fn == "ta.bb":
        src_name = args[0].strip() if len(args) >= 1 else "close"
        length = int(_resolve_scalar(args[1], env)) if len(args) >= 2 else 20
        mult = float(_resolve_scalar(args[2], env)) if len(args) >= 3 else 2.0
        src_key = src_name if src_name in {"open", "high", "low", "close", "hl2", "hlc3"} else "close"
        res = compute_indicator("bb", candles, {"length": length, "mult": mult, "source": src_key})
        return {
            "basis": _align_points(res["basis"]),
            "upper": _align_points(res["upper"]),
            "lower": _align_points(res["lower"]),
        }

    if fn == "ta.supertrend":
        factor = float(_resolve_scalar(args[0], env)) if len(args) >= 1 else 3.0
        atr_len = int(_resolve_scalar(args[1], env)) if len(args) >= 2 else 10
        res = compute_indicator("supertrend", candles, {"atr_length": atr_len, "factor": factor})
        st_arr = _align_points(res["supertrend"])
        dir_arr: list[float | None] = [
            (1.0 if (st is not None and float(c["close"]) >= st) else -1.0) if st is not None else None
            for c, st in zip(candles, st_arr)
        ]
        return {"supertrend": st_arr, "direction": dir_arr}

    raise ValueError(f"Unsupported Pine function '{fn}'")


def _eval_bool_condition(
    cond: str,
    candles: list[dict[str, Any]],
    env: dict[str, Any],
) -> list[bool]:
    c = cond.strip()
    n = len(candles)
    if " and " in c:
        parts = c.split(" and ")
        acc = [True] * n
        for p in parts:
            sub = _eval_bool_condition(p, candles, env)
            acc = [a and b for a, b in zip(acc, sub)]
        return acc
    if " or " in c:
        parts = c.split(" or ")
        acc = [False] * n
        for p in parts:
            sub = _eval_bool_condition(p, candles, env)
            acc = [a or b for a, b in zip(acc, sub)]
        return acc

    if c.startswith("ta.crossover(") or c.startswith("ta.crossunder("):
        is_over = c.startswith("ta.crossover(")
        inner = c[c.index("(") + 1 : c.rindex(")")]
        a_s, b_s = _split_args(inner)[:2]
        la = _resolve_series(a_s, candles, env)
        rb = _resolve_series(b_s, candles, env)
        out = [False] * n
        for i in range(1, n):
            if la[i - 1] is None or rb[i - 1] is None or la[i] is None or rb[i] is None:
                continue
            if is_over:
                out[i] = la[i - 1] <= rb[i - 1] and la[i] > rb[i]
            else:
                out[i] = la[i - 1] >= rb[i - 1] and la[i] < rb[i]
        return out

    for op in (">=", "<=", "==", ">", "<"):
        if op in c:
            l_s, r_s = [p.strip() for p in c.split(op, 1)]
            la = _resolve_series(l_s, candles, env)
            rb = _resolve_series(r_s, candles, env)
            out = [False] * n
            for i in range(n):
                if la[i] is None or rb[i] is None:
                    continue
                if op == ">=":
                    out[i] = la[i] >= rb[i]
                elif op == "<=":
                    out[i] = la[i] <= rb[i]
                elif op == "==":
                    out[i] = la[i] == rb[i]
                elif op == ">":
                    out[i] = la[i] > rb[i]
                elif op == "<":
                    out[i] = la[i] < rb[i]
            return out

    if c in env and isinstance(env[c], list):
        return [bool(v) for v in env[c]]
    raise ValueError(f"Unsupported Pine condition '{cond}'")


def execute_pine_script(
    source: str,
    candles: list[dict[str, Any]],
    input_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Safely interpret a supported Pine v5/v6 AST causally on OHLCV candles (zero eval/exec)."""
    analysis = analyze_pine_script(source)
    compat = analysis["compat_report"]
    if not compat["supported"]:
        raise ValueError(
            "Pine script contains unsupported features: "
            + "; ".join(compat["unsupported_features"])
        )

    n = len(candles)
    overrides = input_overrides or {}
    env: dict[str, Any] = {}
    plots: dict[str, list[dict[str, Any]]] = {}
    entry_signals = [False] * n
    exit_signals = [False] * n

    for stmt in analysis["ast"]["statements"]:
        kind = stmt["kind"]
        if kind == "input":
            name = stmt["name"]
            env[name] = overrides.get(name, stmt["default"])
        elif kind == "assign":
            expr = stmt["expr"]
            if expr.startswith("ta.") and not expr.startswith("ta.cross"):
                res = _eval_ta_call(expr, candles, env)
                env[stmt["target"]] = res["_single"]
            elif expr.startswith("ta.cross"):
                env[stmt["target"]] = _eval_bool_condition(expr, candles, env)
            else:
                env[stmt["target"]] = _resolve_series(expr, candles, env)
        elif kind == "tuple_assign":
            res = _eval_ta_call(stmt["expr"], candles, env)
            targets = stmt["targets"]
            vals = list(res.values())
            for idx, tgt in enumerate(targets):
                if idx < len(vals):
                    env[tgt] = vals[idx]
        elif kind == "plot":
            arr = _resolve_series(stmt["expr"], candles, env)
            plots[stmt["title"]] = [
                {"time": int(c["time"]), "value": round(float(v), 6)}
                for c, v in zip(candles, arr)
                if v is not None
            ]
        elif kind == "strategy_entry" and stmt.get("when"):
            cond_arr = _eval_bool_condition(stmt["when"], candles, env)
            entry_signals = [a or b for a, b in zip(entry_signals, cond_arr)]
        elif kind == "strategy_exit" and stmt.get("when"):
            cond_arr = _eval_bool_condition(stmt["when"], candles, env)
            exit_signals = [a or b for a, b in zip(exit_signals, cond_arr)]

    return {
        "analysis": analysis,
        "plots": plots,
        "entry_signals": entry_signals,
        "exit_signals": exit_signals,
        "entry_count": sum(1 for s in entry_signals if s),
        "exit_count": sum(1 for s in exit_signals if s),
    }
