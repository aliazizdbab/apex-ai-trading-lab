# APEX AI Trading Lab — Pine Script™ Support Matrix (v5 / v6)

This document accurately reflects the implemented parser, analyzer, and sandboxed tree-walking interpreter in [`backend/engine/pine/engine.py`](../backend/engine/pine/engine.py). Execution uses an AST statement walker (`sandbox_mode: "ast_tree_walking_no_eval"`) with **zero `eval()`, `exec()`, or dynamic OS/network access**.

## 1. Script Headers & Declarations

| Construct | Status | Notes |
| --- | --- | --- |
| `//@version=5` / `//@version=6` | Supported | Extracted into `pine_version` |
| `indicator("Title", ...)` | Supported | Sets `script_type = "indicator"` and `title` |
| `strategy("Title", ...)` | Supported | Sets `script_type = "strategy"` and `title` |

## 2. Dynamic Inputs (`input.*`)

Parsed with `default`, `title`, `minval`, and `maxval` metadata for dynamic UI form binding in Pine Studio (`/pine-studio`) and runtime `input_overrides`:

| Input Type | Status | Notes |
| --- | --- | --- |
| `input.int(...)` | Supported | Integer parameters (lengths, lookbacks) |
| `input.float(...)` | Supported | Float parameters (multipliers, thresholds) |
| `input.string(...)` | Supported | String parameters (`source`, mode flags) |
| `input.bool(...)` | Supported | Boolean feature toggles |

## 3. Built-in Series & Expressions

| Construct | Status | Notes |
| --- | --- | --- |
| `open`, `high`, `low`, `close`, `volume` | Supported | Resolved directly from OHLCV candles |
| `hl2`, `hlc3` | Supported | Derived causally per candle |
| Binary arithmetic (`+`, `-`, `*`, `/`) | Supported | Non-parenthesized binary operations between series/scalars; divide-by-zero yields `None` |
| Variable assignment (`x = ...`) | Supported | Scalar literals, series, and `ta.*` single/cross outputs |
| Tuple destructuring (`[a, b, c] = ...`) | Supported | Supported for multi-output `ta.macd`, `ta.bb`, `ta.supertrend` |

## 4. Technical Analysis (`ta.*`) Functions

| Function | Status | Mapped Outputs |
| --- | --- | --- |
| `ta.sma(source, length)` | Supported | Single series |
| `ta.ema(source, length)` | Supported | Single series |
| `ta.rsi(source, length)` | Supported | Single series |
| `ta.macd(source, fast, slow, signal)` | Supported | Tuple `(macd, signal, histogram)` |
| `ta.bb(source, length, mult)` | Supported | Tuple `(basis, upper, lower)` |
| `ta.atr(length)` | Supported | Single series |
| `ta.supertrend(factor, atr_length)` | Supported | Tuple `(supertrend, direction)` |
| `ta.crossover(a, b)` | Supported | Boolean series (`a[1] <= b[1] and a > b`) |
| `ta.crossunder(a, b)` | Supported | Boolean series (`a[1] >= b[1] and a < b`) |

## 5. Strategy Signals, Plots & Alerts

| Construct | Status | Notes |
| --- | --- | --- |
| `plot(series, title=...)` | Supported | Rendered directly onto synced chart pane |
| `strategy.entry(..., when=cond)` or inside `if cond` | Supported | Accumulates causal boolean `entry_signals` |
| `strategy.close(...)` / `strategy.exit(...)` | Supported | Accumulates causal boolean `exit_signals` |
| `alertcondition(...)` | Analyzed | Extracted into `alerts` metadata during static analysis |
| Boolean logic (`and`, `or`, `>=`, `<=`, `==`, `>`, `<`) | Supported | Evaluated element-wise over aligned series |
| `request.security(..., tf, ...)` | Analyzed + Warning | Referenced timeframes extracted into `referenced_timeframes`; `barmerge.lookahead_on`, `barstate.isrealtime`, `barstate.islast` trigger explicit repaint warnings |

## 6. Intentionally Unsupported / Blocked Constructs

Scripts containing any of the following are flagged with `compat_report.supported = false` and rejected safely prior to execution:

- Drawing & layout objects: `line.new`, `label.new`, `box.new`, `table.new`, `polyline.new`
- Dynamic collections: `array.new`, `matrix.new`
- Arbitrary loops, user-defined functions/methods, or unimplemented `ta.*` namespaces raise explicit `ValueError` diagnostics instead of executing unsafe fallbacks.
