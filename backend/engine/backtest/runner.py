from __future__ import annotations

import copy
import math
from typing import Any

from engine.strategy.evaluator import evaluate_strategy


def _compute_metrics(
    initial_capital: float,
    equity_curve: list[dict[str, Any]],
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    if not equity_curve:
        return {
            "initial_capital": initial_capital,
            "final_equity": initial_capital,
            "total_return_pct": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "expectancy_usdt": 0.0,
            "sl_tiebreak_exits": 0,
        }

    final_equity = float(equity_curve[-1]["equity"])
    total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100.0 if initial_capital > 0 else 0.0

    pnls = [float(t["pnl_usdt"]) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total_trades = len(trades)
    win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = 99.99
    else:
        profit_factor = 0.0

    expectancy = (sum(pnls) / total_trades) if total_trades > 0 else 0.0

    peak = initial_capital
    max_dd_pct = 0.0
    drawdown_curve: list[dict[str, Any]] = []
    for pt in equity_curve:
        eq = float(pt["equity"])
        if eq > peak:
            peak = eq
        dd_pct = ((peak - eq) / peak) * 100.0 if peak > 0 else 0.0
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
        drawdown_curve.append({"time": pt["time"], "drawdown_pct": round(dd_pct, 4)})

    returns: list[float] = []
    for i in range(1, len(equity_curve)):
        prev_eq = float(equity_curve[i - 1]["equity"])
        curr_eq = float(equity_curve[i]["equity"])
        if prev_eq > 0:
            returns.append((curr_eq - prev_eq) / prev_eq)

    sharpe = 0.0
    sortino = 0.0
    if len(returns) >= 2:
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std_r = math.sqrt(var_r)
        if std_r > 1e-12:
            sharpe = (mean_r / std_r) * math.sqrt(len(returns))
        downside = [r for r in returns if r < 0]
        if downside:
            down_var = sum(r ** 2 for r in downside) / len(returns)
            down_std = math.sqrt(down_var)
            if down_std > 1e-12:
                sortino = (mean_r / down_std) * math.sqrt(len(returns))

    sl_tiebreak_exits = sum(1 for t in trades if t.get("exit_reason") == "stop_loss_tiebreak")

    return {
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 4),
        "total_trades": total_trades,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown_pct": round(max_dd_pct, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "expectancy_usdt": round(expectancy, 4),
        "sl_tiebreak_exits": sl_tiebreak_exits,
        "drawdown_curve": drawdown_curve,
    }


def run_event_driven_backtest(
    definition: dict[str, Any],
    candles: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Reference event-driven Spot backtester:
    - Signal at close of bar N executes at open of bar N+1.
    - Fees and slippage applied conservatively on entry and exit.
    - Intrabar SL/TP conflict assumes conservative Stop-Loss execution first.
    """
    cfg = config or {}
    initial_capital = float(cfg.get("initial_capital_usdt", 10000.0))
    position_size_pct = float(cfg.get("position_size_pct", 95.0))
    fixed_capital = float(cfg.get("fixed_capital_usdt", 0.0))
    fee_rate = float(cfg.get("fee_pct", 0.1)) / 100.0
    slip_rate = float(cfg.get("slippage_pct", 0.05)) / 100.0

    eval_out = evaluate_strategy(definition, candles)
    defn = eval_out["definition"]
    entry_signals = eval_out["entry_signals"]
    exit_signals = eval_out["exit_signals"]

    sl_pct = float(defn["stop_loss_pct"]) / 100.0
    tp_pct = float(defn["take_profit_pct"]) / 100.0

    cash = initial_capital
    pos_qty = 0.0
    entry_price = 0.0
    entry_cost = 0.0
    entry_time = 0
    sl_price = 0.0
    tp_price = 0.0

    trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []

    for i, bar in enumerate(candles):
        t = int(bar["time"])
        o = float(bar["open"])
        h = float(bar["high"])
        l = float(bar["low"])
        c = float(bar["close"])

        # 1) Execute pending open-of-bar entry/exit from bar (i - 1) close signal
        if i > 0:
            if pos_qty > 0 and exit_signals[i - 1]:
                exec_px = o * (1.0 - slip_rate)
                gross_proceeds = pos_qty * exec_px
                fee = gross_proceeds * fee_rate
                net_proceeds = gross_proceeds - fee
                pnl = net_proceeds - entry_cost
                pnl_pct = (pnl / entry_cost) * 100.0 if entry_cost > 0 else 0.0
                cash += net_proceeds
                trades.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": t,
                        "entry_price": round(entry_price, 6),
                        "exit_price": round(exec_px, 6),
                        "qty": round(pos_qty, 8),
                        "pnl_usdt": round(pnl, 4),
                        "pnl_pct": round(pnl_pct, 4),
                        "fee_usdt": round(fee, 4),
                        "exit_reason": "signal",
                    }
                )
                pos_qty = 0.0
                entry_cost = 0.0

            elif pos_qty == 0.0 and entry_signals[i - 1]:
                alloc = fixed_capital if fixed_capital > 0 else cash * (position_size_pct / 100.0)
                alloc = min(alloc, cash)
                if alloc > 1.0:
                    exec_px = o * (1.0 + slip_rate)
                    qty = alloc / (exec_px * (1.0 + fee_rate))
                    fee = (qty * exec_px) * fee_rate
                    total_spent = qty * exec_px + fee
                    cash -= total_spent
                    pos_qty = qty
                    entry_price = exec_px
                    entry_cost = total_spent
                    entry_time = t
                    sl_price = entry_price * (1.0 - sl_pct)
                    tp_price = entry_price * (1.0 + tp_pct)

        # 2) Intrabar SL/TP check with conservative SL tie-breaker
        if pos_qty > 0:
            hit_sl = l <= sl_price
            hit_tp = h >= tp_price
            if hit_sl:
                reason = "stop_loss_tiebreak" if hit_tp else "stop_loss"
                exec_px = sl_price * (1.0 - slip_rate)
                gross_proceeds = pos_qty * exec_px
                fee = gross_proceeds * fee_rate
                net_proceeds = gross_proceeds - fee
                pnl = net_proceeds - entry_cost
                pnl_pct = (pnl / entry_cost) * 100.0 if entry_cost > 0 else 0.0
                cash += net_proceeds
                trades.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": t,
                        "entry_price": round(entry_price, 6),
                        "exit_price": round(exec_px, 6),
                        "qty": round(pos_qty, 8),
                        "pnl_usdt": round(pnl, 4),
                        "pnl_pct": round(pnl_pct, 4),
                        "fee_usdt": round(fee, 4),
                        "exit_reason": reason,
                    }
                )
                pos_qty = 0.0
                entry_cost = 0.0
            elif hit_tp:
                exec_px = tp_price * (1.0 - slip_rate)
                gross_proceeds = pos_qty * exec_px
                fee = gross_proceeds * fee_rate
                net_proceeds = gross_proceeds - fee
                pnl = net_proceeds - entry_cost
                pnl_pct = (pnl / entry_cost) * 100.0 if entry_cost > 0 else 0.0
                cash += net_proceeds
                trades.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": t,
                        "entry_price": round(entry_price, 6),
                        "exit_price": round(exec_px, 6),
                        "qty": round(pos_qty, 8),
                        "pnl_usdt": round(pnl, 4),
                        "pnl_pct": round(pnl_pct, 4),
                        "fee_usdt": round(fee, 4),
                        "exit_reason": "take_profit",
                    }
                )
                pos_qty = 0.0
                entry_cost = 0.0

        mark_equity = cash + (pos_qty * c)
        equity_curve.append({"time": t, "equity": round(mark_equity, 2)})

    metrics = _compute_metrics(initial_capital, equity_curve, trades)
    drawdown_curve = metrics.pop("drawdown_curve", [])

    return {
        "engine": "event_driven",
        "metrics": metrics,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trades": trades,
        "entry_signals": entry_signals,
        "exit_signals": exit_signals,
    }


def run_vectorized_backtest(
    definition: dict[str, Any],
    candles: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fast vectorized signal sweep sharing the exact StrategyEvaluator rules."""
    eval_out = evaluate_strategy(definition, candles)
    entry_signals = eval_out["entry_signals"]
    exit_signals = eval_out["exit_signals"]

    # Approximate vectorized next-bar open return summary for rapid parameter grid ranking
    cfg = config or {}
    fee_rate = float(cfg.get("fee_pct", 0.1)) / 100.0
    in_pos = False
    entry_px = 0.0
    cumulative = 1.0
    trades_count = 0

    for i in range(1, len(candles)):
        open_px = float(candles[i]["open"])
        if not in_pos and entry_signals[i - 1]:
            in_pos = True
            entry_px = open_px * (1.0 + fee_rate)
        elif in_pos and exit_signals[i - 1]:
            in_pos = False
            exit_px = open_px * (1.0 - fee_rate)
            if entry_px > 0:
                cumulative *= exit_px / entry_px
                trades_count += 1

    return {
        "engine": "vectorized",
        "entry_signals": entry_signals,
        "exit_signals": exit_signals,
        "approx_return_pct": round((cumulative - 1.0) * 100.0, 4),
        "signal_entries": sum(1 for s in entry_signals if s),
        "signal_exits": sum(1 for s in exit_signals if s),
        "approx_trades": trades_count,
    }


def run_walk_forward_optimization(
    definition: dict[str, Any],
    candles: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Perform In-Sample (70%) / Out-of-Sample (30%) Walk-Forward test and sensitivity grid."""
    if len(candles) < 40:
        raise ValueError("Walk-forward optimization requires at least 40 candles")

    split_idx = int(len(candles) * 0.7)
    is_candles = candles[:split_idx]
    oos_candles = candles[split_idx:]

    grid_results: list[dict[str, Any]] = []
    sl_grid = [1.0, 1.5, 2.5]
    tp_grid = [2.0, 3.5, 5.0]

    best_candidate: dict[str, Any] | None = None
    best_score = -1e18

    for sl in sl_grid:
        for tp in tp_grid:
            cand = copy.deepcopy(definition)
            cand["stop_loss_pct"] = sl
            cand["take_profit_pct"] = tp
            is_res = run_event_driven_backtest(cand, is_candles, config)
            m = is_res["metrics"]
            score = float(m["total_return_pct"]) - (0.5 * float(m["max_drawdown_pct"]))
            row = {
                "stop_loss_pct": sl,
                "take_profit_pct": tp,
                "is_return_pct": m["total_return_pct"],
                "is_win_rate_pct": m["win_rate_pct"],
                "is_max_drawdown_pct": m["max_drawdown_pct"],
                "is_trades": m["total_trades"],
                "score": round(score, 4),
            }
            grid_results.append(row)
            if score > best_score:
                best_score = score
                best_candidate = cand

    assert best_candidate is not None
    is_best = run_event_driven_backtest(best_candidate, is_candles, config)
    oos_best = run_event_driven_backtest(best_candidate, oos_candles, config)

    is_ret = float(is_best["metrics"]["total_return_pct"])
    oos_ret = float(oos_best["metrics"]["total_return_pct"])
    overfitting_warning = bool(is_ret > 0 and (oos_ret < 0 or oos_ret < is_ret * 0.3))

    return {
        "split_index": split_idx,
        "in_sample_bars": len(is_candles),
        "out_of_sample_bars": len(oos_candles),
        "best_params": {
            "stop_loss_pct": best_candidate["stop_loss_pct"],
            "take_profit_pct": best_candidate["take_profit_pct"],
        },
        "in_sample_metrics": is_best["metrics"],
        "out_of_sample_metrics": oos_best["metrics"],
        "overfitting_warning": overfitting_warning,
        "overfitting_reason": (
            "Out-of-sample performance degraded significantly relative to in-sample."
            if overfitting_warning
            else "Out-of-sample behavior remained consistent with in-sample regime."
        ),
        "sensitivity_grid": sorted(grid_results, key=lambda r: r["score"], reverse=True),
    }
