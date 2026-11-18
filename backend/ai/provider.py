from __future__ import annotations

from typing import Any

from engine.strategy.evaluator import validate_strategy_definition


class AIProviderManager:
    """
    AI Strategy Builder & Quantitative Research Assistant abstraction.
    Always produces Draft strategies or pending suggestions; never imports or invokes any Broker.
    """

    def generate_strategy_draft(
        self,
        prompt: str,
        *,
        symbol: str = "BTC/USDT",
        timeframe: str = "15m",
        gemini_configured: bool = False,
    ) -> dict[str, Any]:
        """Synthesize a validated Draft multi-indicator StrategyDefinition from a prompt."""
        lower = prompt.lower()
        clean_symbol = symbol.strip().upper()

        if "mean" in lower or "reversion" in lower or "bollinger" in lower or "oversold" in lower:
            name = f"AI Mean Reversion ({clean_symbol})"
            description = (
                "Synthesized mean-reversion strategy combining Bollinger Bands, RSI oversold/overbought, "
                "Stochastic confirmation, and ATR volatility filtering."
            )
            raw_defn = {
                "symbol": clean_symbol,
                "timeframe": timeframe,
                "signal_mode": "closed_candle",
                "stop_loss_pct": 1.8,
                "take_profit_pct": 3.2,
                "indicators": [
                    {"key": "bb_main", "indicator_id": "bb", "params": {"length": 20, "mult": 2.0}},
                    {"key": "rsi_main", "indicator_id": "rsi", "params": {"length": 14}},
                    {"key": "stoch_main", "indicator_id": "stoch", "params": {"k_length": 14, "k_smoothing": 3, "d_length": 3}},
                    {"key": "ema_trend", "indicator_id": "ema", "params": {"length": 50}},
                    {"key": "atr_vol", "indicator_id": "atr", "params": {"length": 14}},
                    {"key": "adx_str", "indicator_id": "adx", "params": {"di_length": 14, "adx_smoothing": 14}},
                ],
                "entry_rule": {
                    "type": "AND",
                    "children": [
                        {"type": "COMPARE", "left": "price.close", "op": "<=", "right": "bb_main.lower"},
                        {"type": "COMPARE", "left": "rsi_main.rsi", "op": "<", "right": 35},
                        {"type": "COMPARE", "left": "stoch_main.k", "op": "<", "right": 30},
                    ],
                },
                "exit_rule": {
                    "type": "OR",
                    "children": [
                        {"type": "COMPARE", "left": "price.close", "op": ">=", "right": "bb_main.basis"},
                        {"type": "COMPARE", "left": "rsi_main.rsi", "op": ">", "right": 68},
                    ],
                },
            }
        elif "supertrend" in lower or "breakout" in lower or "trend" in lower:
            name = f"AI Supertrend Breakout ({clean_symbol})"
            description = (
                "Trend-following strategy combining Supertrend, ADX trend strength, EMA filter, "
                "MACD momentum, and VWAP anchor."
            )
            raw_defn = {
                "symbol": clean_symbol,
                "timeframe": timeframe,
                "signal_mode": "closed_candle",
                "stop_loss_pct": 2.0,
                "take_profit_pct": 4.5,
                "indicators": [
                    {"key": "st_main", "indicator_id": "supertrend", "params": {"atr_length": 10, "factor": 3.0}},
                    {"key": "ema_fast", "indicator_id": "ema", "params": {"length": 20}},
                    {"key": "ema_slow", "indicator_id": "ema", "params": {"length": 50}},
                    {"key": "adx_main", "indicator_id": "adx", "params": {"di_length": 14, "adx_smoothing": 14}},
                    {"key": "macd_main", "indicator_id": "macd", "params": {}},
                    {"key": "vwap_main", "indicator_id": "vwap", "params": {"anchor": "session"}},
                ],
                "entry_rule": {
                    "type": "AND",
                    "children": [
                        {"type": "COMPARE", "left": "price.close", "op": ">", "right": "st_main.supertrend"},
                        {"type": "COMPARE", "left": "ema_fast.ema", "op": ">", "right": "ema_slow.ema"},
                        {"type": "COMPARE", "left": "adx_main.adx", "op": ">", "right": 20},
                    ],
                },
                "exit_rule": {
                    "type": "OR",
                    "children": [
                        {"type": "COMPARE", "left": "price.close", "op": "<", "right": "st_main.supertrend"},
                        {"type": "CROSS_BELOW", "left": "macd_main.macd", "right": "macd_main.signal"},
                    ],
                },
            }
        else:
            name = f"AI Momentum Confluence ({clean_symbol})"
            description = (
                "Multi-indicator momentum strategy combining EMA crossover, RSI filter, MACD confirmation, "
                "Bollinger basis, VWAP, and ATR volatility."
            )
            raw_defn = {
                "symbol": clean_symbol,
                "timeframe": timeframe,
                "signal_mode": "closed_candle",
                "stop_loss_pct": 1.5,
                "take_profit_pct": 3.5,
                "indicators": [
                    {"key": "ema_fast", "indicator_id": "ema", "params": {"length": 9}},
                    {"key": "ema_slow", "indicator_id": "ema", "params": {"length": 21}},
                    {"key": "rsi_main", "indicator_id": "rsi", "params": {"length": 14}},
                    {"key": "macd_main", "indicator_id": "macd", "params": {}},
                    {"key": "bb_main", "indicator_id": "bb", "params": {"length": 20, "mult": 2.0}},
                    {"key": "atr_main", "indicator_id": "atr", "params": {"length": 14}},
                ],
                "entry_rule": {
                    "type": "AND",
                    "children": [
                        {"type": "CROSS_ABOVE", "left": "ema_fast.ema", "right": "ema_slow.ema"},
                        {"type": "COMPARE", "left": "rsi_main.rsi", "op": ">", "right": 50},
                        {"type": "COMPARE", "left": "macd_main.histogram", "op": ">", "right": 0},
                    ],
                },
                "exit_rule": {
                    "type": "OR",
                    "children": [
                        {"type": "CROSS_BELOW", "left": "ema_fast.ema", "right": "ema_slow.ema"},
                        {"type": "COMPARE", "left": "rsi_main.rsi", "op": ">", "right": 75},
                    ],
                },
            }

        validated_defn = validate_strategy_definition(raw_defn)
        return {
            "provider_used": "gemini_ready_quant_synthesizer" if gemini_configured else "apex_quant_local",
            "status": "Draft",
            "name": name,
            "description": description,
            "definition": validated_defn,
            "explanation": (
                f"Generated Draft strategy '{name}' with {len(validated_defn['indicators'])} validated indicators. "
                "Must pass historical backtesting and owner approval before Paper or Live deployment."
            ),
        }

    def analyze_strategy_research(
        self,
        *,
        strategy_name: str,
        metrics: dict[str, Any],
        symbol: str,
        gemini_configured: bool = False,
    ) -> dict[str, Any]:
        """Generate structured performance review and a pending optimization suggestion."""
        ret = float(metrics.get("total_return_pct", 0.0))
        dd = float(metrics.get("max_drawdown_pct", 0.0))
        win_rate = float(metrics.get("win_rate_pct", 0.0))
        pf = float(metrics.get("profit_factor", 0.0))
        trades = int(metrics.get("total_trades", 0))

        findings: list[str] = []
        if trades < 10:
            findings.append(f"Sample size is small ({trades} trades); widen historical window before live capital.")
        if dd > 10.0:
            findings.append(f"Max drawdown ({dd:.2f}%) exceeds 10%; tighten stop_loss_pct or add ADX regime filter.")
        if pf < 1.2 and trades > 0:
            findings.append(f"Profit factor ({pf:.2f}) is modest; consider higher take_profit_pct or stricter entry filter.")
        if win_rate >= 55.0 and pf >= 1.3:
            findings.append(f"Healthy win rate ({win_rate:.1f}%) and profit factor ({pf:.2f}) on {symbol}.")
        if not findings:
            findings.append(f"Baseline return {ret:.2f}% over {trades} trades recorded. Ready for walk-forward verification.")

        suggested_sl = round(max(0.8, min(3.0, 1.2 if dd > 8 else 1.5)), 2)
        suggested_tp = round(suggested_sl * 2.4, 2)

        return {
            "provider_used": "gemini_ready_quant_analyst" if gemini_configured else "apex_quant_local",
            "summary": " ".join(findings),
            "proposal": {
                "recommended_stop_loss_pct": suggested_sl,
                "recommended_take_profit_pct": suggested_tp,
                "require_walk_forward": True,
            },
            "status": "pending",
        }

    def build_market_intelligence(self, tickers: list[dict[str, Any]]) -> dict[str, Any]:
        """Classify live market regime, breadth, and volatility leaders from MEXC Spot tickers."""
        if not tickers:
            return {
                "regime": "Unavailable",
                "breadth_pct": 0.0,
                "avg_change_pct": 0.0,
                "volatility_leaders": [],
                "momentum_leaders": [],
            }

        advancers = sum(1 for t in tickers if float(t.get("change24h", 0.0)) >= 0)
        breadth_pct = (advancers / len(tickers)) * 100.0
        avg_change = sum(float(t.get("change24h", 0.0)) for t in tickers) / len(tickers)

        if breadth_pct >= 65.0 and avg_change > 1.0:
            regime = "Bullish Expansion"
        elif breadth_pct <= 35.0 and avg_change < -1.0:
            regime = "Bearish Pressure"
        else:
            regime = "Range / Mixed Consolidation"

        ranked_vol = sorted(
            tickers,
            key=lambda r: ((float(r.get("high", 0)) - float(r.get("low", 0))) / max(float(r.get("last", 1)), 1e-9)),
            reverse=True,
        )[:5]

        ranked_mom = sorted(tickers, key=lambda r: float(r.get("change24h", 0.0)), reverse=True)[:5]

        return {
            "regime": regime,
            "breadth_pct": round(breadth_pct, 2),
            "avg_change_pct": round(avg_change, 4),
            "volatility_leaders": [
                {
                    "symbol": r["symbol"],
                    "last": r["last"],
                    "range_pct": round(
                        ((float(r["high"]) - float(r["low"])) / max(float(r["last"]), 1e-9)) * 100.0, 2
                    ),
                }
                for r in ranked_vol
            ],
            "momentum_leaders": [
                {"symbol": r["symbol"], "last": r["last"], "change24h": r["change24h"]}
                for r in ranked_mom
            ],
        }
