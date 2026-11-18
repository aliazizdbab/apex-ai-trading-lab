from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

import httpx

PROVIDER_CATALOG: dict[str, dict[str, str]] = {
    "builtin": {
        "label": "APEX Built-in Quant Copilot (Local Tool Engine)",
        "default_model": "apex-quant-copilot-v1",
        "base_url": "",
    },
    "gemini": {
        "label": "Google Gemini API",
        "default_model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
    },
    "openai": {
        "label": "OpenAI API",
        "default_model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
    },
    "anthropic": {
        "label": "Anthropic Claude API",
        "default_model": "claude-3-7-sonnet-latest",
        "base_url": "https://api.anthropic.com/v1",
    },
    "deepseek": {
        "label": "DeepSeek API",
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
    },
    "openrouter": {
        "label": "OpenRouter API",
        "default_model": "openai/gpt-4o-mini",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "custom": {
        "label": "Custom OpenAI-Compatible Endpoint",
        "default_model": "custom-model",
        "base_url": "http://127.0.0.1:11434/v1",
    },
}

COPILOT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_strategy",
        "description": "Create and persist a new validated 6+ indicator trading strategy in the Strategy Library.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Descriptive strategy name."},
                "symbol": {"type": "string", "description": "Spot trading pair, e.g. BTC/USDT, ETH/USDT, SOL/USDT."},
                "timeframe": {"type": "string", "description": "Candle timeframe: 1m, 5m, 15m, 1h, 4h, 1D."},
                "style": {
                    "type": "string",
                    "enum": ["momentum", "mean_reversion", "trend"],
                    "description": "Quantitative strategy style.",
                },
                "stop_loss_pct": {"type": "number", "description": "Conservative stop loss percentage (e.g. 1.5)."},
                "take_profit_pct": {"type": "number", "description": "Take profit percentage (e.g. 3.5)."},
            },
            "required": ["symbol", "timeframe"],
        },
    },
    {
        "name": "modify_strategy",
        "description": "Modify an existing strategy's parameters/timeframe/status and create a new immutable StrategyVersion.",
        "parameters": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string", "description": "Strategy UUID (omit to target active strategy)."},
                "stop_loss_pct": {"type": "number"},
                "take_profit_pct": {"type": "number"},
                "timeframe": {"type": "string"},
                "symbol": {"type": "string"},
                "status": {"type": "string"},
                "change_note": {"type": "string"},
            },
        },
    },
    {
        "name": "run_backtest",
        "description": "Run a deterministic event-driven + vectorized backtest over historical candles and store the BacktestJob.",
        "parameters": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string", "description": "Target strategy ID (defaults to active strategy)."},
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
                "bars": {"type": "integer", "description": "Number of historical bars (120..1000)."},
                "initial_capital_usdt": {"type": "number"},
            },
        },
    },
    {
        "name": "run_walk_forward",
        "description": "Run 70% In-Sample / 30% Out-of-Sample Walk-Forward optimization and optionally save a new version with best parameters.",
        "parameters": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string"},
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
                "bars": {"type": "integer"},
                "apply_best_params": {"type": "boolean"},
            },
        },
    },
    {
        "name": "evaluate_signals",
        "description": "Evaluate live entry/exit signals and confluence score on recent candles for a strategy.",
        "parameters": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string"},
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
            },
        },
    },
    {
        "name": "execute_paper_order",
        "description": "Place a virtual Spot order in the strictly isolated Paper Trading account after RiskEngine checks.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "qty": {"type": "number"},
            },
            "required": ["symbol", "side", "qty"],
        },
    },
    {
        "name": "update_risk_profile",
        "description": "Update global RiskEngine thresholds (per-trade risk %, daily loss %, max drawdown %, max open positions).",
        "parameters": {
            "type": "object",
            "properties": {
                "max_risk_per_trade_pct": {"type": "number"},
                "max_daily_loss_pct": {"type": "number"},
                "max_drawdown_pct": {"type": "number"},
                "max_open_positions": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_market_intelligence",
        "description": "Fetch live MEXC Spot market regime, breadth percentage, volatility leaders, and momentum leaders.",
        "parameters": {"type": "object", "properties": {}},
    },
]

_KNOWN_COINS = ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE", "LINK", "ARB", "INJ", "OP", "SUI")
_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1D", "1W")


def _has_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


def _resolve_base_url(provider: str, custom_base_url: str | None) -> str:
    if custom_base_url and custom_base_url.strip():
        return custom_base_url.strip().rstrip("/")
    return PROVIDER_CATALOG.get(provider, PROVIDER_CATALOG["openai"])["base_url"].rstrip("/")


def _extract_symbol(text: str, default: str = "BTC/USDT") -> str:
    pair_m = re.search(r"\b([A-Za-z]{2,10})/USDT\b", text, re.IGNORECASE)
    if pair_m:
        return f"{pair_m.group(1).upper()}/USDT"
    upper = text.upper()
    for coin in _KNOWN_COINS:
        if re.search(rf"\b{coin}\b", upper):
            return f"{coin}/USDT"
    return default


def _extract_timeframe(text: str, default: str = "15m") -> str:
    lower = text.lower()
    for tf in sorted(_TIMEFRAMES, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(tf.lower())}(?![a-z0-9])", lower):
            return tf
    if "ساعة" in text or "hourly" in lower:
        return "1h"
    if "4 ساعات" in text:
        return "4h"
    if "يومي" in text or "daily" in lower:
        return "1D"
    return default


def _extract_style(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("mean", "reversion", "bollinger", "oversold", "ارتداد", "انعكاس", "بولينجر", "تشبع")):
        return "mean_reversion"
    if any(w in lower for w in ("supertrend", "breakout", "trend", "اتجاه", "سوبرترند", "اختراق")):
        return "trend"
    return "momentum"


def _extract_pct_after(text: str, keywords: tuple[str, ...]) -> float | None:
    lower = text.lower()
    for kw in keywords:
        m = re.search(rf"{re.escape(kw)}[^\d]{{0,18}}(\d+(?:\.\d+)?)\s*%?", lower)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def _build_system_prompt(app_state: dict[str, Any], custom_instructions: str, autonomy_level: str) -> str:
    summary = {
        "autonomy_level": autonomy_level,
        "active_page": app_state.get("active_page", "/"),
        "strategies_count": len(app_state.get("strategies", [])),
        "strategies": [
            {
                "id": s["id"],
                "name": s["name"],
                "status": s["status"],
                "symbol": s.get("symbol"),
                "timeframe": s.get("timeframe"),
                "stop_loss_pct": s.get("stop_loss_pct"),
                "take_profit_pct": s.get("take_profit_pct"),
            }
            for s in app_state.get("strategies", [])[:8]
        ],
        "recent_backtests": app_state.get("recent_backtests", [])[:6],
        "paper_account": app_state.get("paper_account", {}),
        "risk_profile": app_state.get("risk_profile", {}),
    }
    base = (
        "You are APEX Quant Copilot, the owner's embedded quantitative trading partner inside APEX AI Trading Lab "
        "(MEXC Spot Platform). You have FULL access to the platform's deterministic Python tools via function calls: "
        "creating 6+ indicator strategies, modifying StrategyVersions, running historical backtests, running 70/30 "
        "Walk-Forward optimizations, evaluating live entry/exit signals, placing Paper Trading virtual orders, "
        "updating RiskEngine limits, and reading live Market Intelligence.\n"
        "Rules:\n"
        "1. Always reply in the user's language (Arabic when user writes Arabic; English when English).\n"
        "2. When asked to create, edit, backtest, optimize, evaluate signals, or trade paper, CALL the corresponding tools "
        "rather than merely describing what could be done. Chain tools logically (e.g. create_strategy -> run_backtest).\n"
        "3. Never fabricate backtest metrics or prices; cite exact metrics returned by tools.\n"
        "4. Respect strict Paper vs Real separation: automated orders via chat run on Paper only.\n"
        f"Current App Snapshot:\n{json.dumps(summary, ensure_ascii=False)}"
    )
    if custom_instructions.strip():
        base += f"\nOwner Custom Instructions:\n{custom_instructions.strip()}"
    return base


class CopilotAgent:
    """Multi-provider Agentic Quant Copilot orchestrator supporting tool calling across the entire APEX app."""

    def test_connection(
        self,
        *,
        provider: str,
        model_name: str,
        api_key: str | None,
        base_url: str | None,
    ) -> dict[str, Any]:
        clean_provider = provider if provider in PROVIDER_CATALOG else "builtin"
        resolved_model = model_name.strip() or PROVIDER_CATALOG[clean_provider]["default_model"]
        t0 = time.perf_counter()

        if clean_provider == "builtin":
            return {
                "ok": True,
                "provider": "builtin",
                "model_name": resolved_model,
                "latency_ms": 2,
                "message": "Built-in APEX Quantitative Copilot is ready with full internal tool access.",
            }

        if not api_key or len(api_key.strip()) < 6:
            return {
                "ok": False,
                "provider": clean_provider,
                "model_name": resolved_model,
                "latency_ms": 0,
                "message": f"API key is missing for provider '{clean_provider}'.",
            }

        key = api_key.strip()
        try:
            with httpx.Client(timeout=12.0) as client:
                if clean_provider == "gemini":
                    url = (
                        f"https://generativelanguage.googleapis.com/v1beta/models/"
                        f"{resolved_model}:generateContent?key={key}"
                    )
                    resp = client.post(
                        url,
                        json={"contents": [{"parts": [{"text": "Reply only with OK."}]}]},
                    )
                elif clean_provider == "anthropic":
                    resp = client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": resolved_model,
                            "max_tokens": 16,
                            "messages": [{"role": "user", "content": "Reply only with OK."}],
                        },
                    )
                else:
                    endpoint = f"{_resolve_base_url(clean_provider, base_url)}/chat/completions"
                    resp = client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json={
                            "model": resolved_model,
                            "max_tokens": 16,
                            "messages": [{"role": "user", "content": "Reply only with OK."}],
                        },
                    )

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if resp.status_code >= 400:
                detail = resp.text[:220]
                return {
                    "ok": False,
                    "provider": clean_provider,
                    "model_name": resolved_model,
                    "latency_ms": elapsed_ms,
                    "message": f"Provider returned HTTP {resp.status_code}: {detail}",
                }
            return {
                "ok": True,
                "provider": clean_provider,
                "model_name": resolved_model,
                "latency_ms": elapsed_ms,
                "message": f"Connected successfully to {clean_provider} ({resolved_model}) in {elapsed_ms} ms.",
            }
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "ok": False,
                "provider": clean_provider,
                "model_name": resolved_model,
                "latency_ms": elapsed_ms,
                "message": f"Connection check failed: {exc}",
            }

    def run_turn(
        self,
        *,
        message: str,
        history: list[dict[str, Any]],
        app_state: dict[str, Any],
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        provider: str,
        model_name: str,
        api_key: str | None,
        base_url: str | None,
        autonomy_level: str,
        system_instructions: str,
        language_hint: str = "en",
    ) -> dict[str, Any]:
        """Run a conversational agent turn using the configured external LLM (with tool calling) or built-in engine."""
        clean_provider = provider if provider in PROVIDER_CATALOG else "builtin"
        resolved_model = model_name.strip() or PROVIDER_CATALOG[clean_provider]["default_model"]
        sys_prompt = _build_system_prompt(app_state, system_instructions, autonomy_level)

        if clean_provider != "builtin" and api_key and api_key.strip():
            try:
                if clean_provider == "gemini":
                    reply, actions = self._run_gemini_loop(
                        message=message,
                        history=history,
                        system_prompt=sys_prompt,
                        model_name=resolved_model,
                        api_key=api_key.strip(),
                        tool_executor=tool_executor,
                    )
                elif clean_provider == "anthropic":
                    reply, actions = self._run_anthropic_loop(
                        message=message,
                        history=history,
                        system_prompt=sys_prompt,
                        model_name=resolved_model,
                        api_key=api_key.strip(),
                        tool_executor=tool_executor,
                    )
                else:
                    reply, actions = self._run_openai_compat_loop(
                        message=message,
                        history=history,
                        system_prompt=sys_prompt,
                        model_name=resolved_model,
                        api_key=api_key.strip(),
                        base_url=_resolve_base_url(clean_provider, base_url),
                        tool_executor=tool_executor,
                    )
                return {
                    "reply": reply,
                    "provider_used": f"{clean_provider}:{resolved_model}",
                    "tool_actions": actions,
                    "quick_prompts": self._suggest_quick_prompts(message, language_hint, actions),
                    "fallback_warning": None,
                }
            except Exception as exc:
                fallback = self._run_builtin_quant_agent(
                    message=message,
                    app_state=app_state,
                    tool_executor=tool_executor,
                    language_hint=language_hint,
                )
                fallback["fallback_warning"] = f"External provider {clean_provider} error ({exc}); executed via Built-in Quant Engine."
                return fallback

        return self._run_builtin_quant_agent(
            message=message,
            app_state=app_state,
            tool_executor=tool_executor,
            language_hint=language_hint,
        )

    def _run_openai_compat_loop(
        self,
        *,
        message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
        model_name: str,
        api_key: str,
        base_url: str,
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for item in history[-10:]:
            role = item.get("role", "user")
            if role in {"user", "assistant"} and item.get("content"):
                messages.append({"role": role, "content": str(item["content"])})
        messages.append({"role": "user", "content": message})

        oai_tools = [{"type": "function", "function": t} for t in COPILOT_TOOLS]
        tool_actions: list[dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        with httpx.Client(timeout=35.0) as client:
            for _ in range(4):
                resp = client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json={"model": model_name, "messages": messages, "tools": oai_tools, "temperature": 0.2},
                )
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]["message"]
                calls = choice.get("tool_calls") or []
                if not calls:
                    return str(choice.get("content") or "").strip(), tool_actions

                messages.append(choice)
                for call in calls:
                    fn_name = call["function"]["name"]
                    raw_args = call["function"].get("arguments") or "{}"
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                    result = tool_executor(fn_name, args)
                    tool_actions.append(result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

        return "Completed requested tool executions.", tool_actions

    def _run_gemini_loop(
        self,
        *,
        message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
        model_name: str,
        api_key: str,
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        contents: list[dict[str, Any]] = []
        for item in history[-10:]:
            role = "model" if item.get("role") == "assistant" else "user"
            if item.get("content"):
                contents.append({"role": role, "parts": [{"text": str(item["content"])}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        tool_actions: list[dict[str, Any]] = []
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        with httpx.Client(timeout=35.0) as client:
            for _ in range(4):
                resp = client.post(
                    url,
                    json={
                        "system_instruction": {"parts": [{"text": system_prompt}]},
                        "contents": contents,
                        "tools": [{"functionDeclarations": COPILOT_TOOLS}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                candidate = data["candidates"][0]["content"]
                parts = candidate.get("parts") or []
                fn_calls = [p["functionCall"] for p in parts if "functionCall" in p]
                if not fn_calls:
                    text = "\n".join(p.get("text", "") for p in parts if "text" in p).strip()
                    return text, tool_actions

                contents.append(candidate)
                fn_responses = []
                for fc in fn_calls:
                    fn_name = fc["name"]
                    args = fc.get("args") or {}
                    result = tool_executor(fn_name, args)
                    tool_actions.append(result)
                    fn_responses.append({"functionResponse": {"name": fn_name, "response": result}})
                contents.append({"role": "user", "parts": fn_responses})

        return "Completed Gemini tool chain.", tool_actions

    def _run_anthropic_loop(
        self,
        *,
        message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
        model_name: str,
        api_key: str,
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        messages: list[dict[str, Any]] = []
        for item in history[-10:]:
            role = item.get("role", "user")
            if role in {"user", "assistant"} and item.get("content"):
                messages.append({"role": role, "content": str(item["content"])})
        messages.append({"role": "user", "content": message})

        claude_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in COPILOT_TOOLS
        ]
        tool_actions: list[dict[str, Any]] = []
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        with httpx.Client(timeout=35.0) as client:
            for _ in range(4):
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json={
                        "model": model_name,
                        "max_tokens": 2048,
                        "system": system_prompt,
                        "tools": claude_tools,
                        "messages": messages,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                blocks = data.get("content") or []
                tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
                if not tool_uses:
                    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
                    return text, tool_actions

                messages.append({"role": "assistant", "content": blocks})
                tool_results = []
                for tu in tool_uses:
                    result = tool_executor(tu["name"], tu.get("input") or {})
                    tool_actions.append(result)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                messages.append({"role": "user", "content": tool_results})

        return "Completed Anthropic tool chain.", tool_actions

    def _run_builtin_quant_agent(
        self,
        *,
        message: str,
        app_state: dict[str, Any],
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        language_hint: str,
    ) -> dict[str, Any]:
        is_ar = _has_arabic(message) or language_hint == "ar"
        lower = message.lower()
        strategies = app_state.get("strategies", [])
        active_strat = strategies[0] if strategies else None

        symbol = _extract_symbol(message, active_strat.get("symbol", "BTC/USDT") if active_strat else "BTC/USDT")
        timeframe = _extract_timeframe(message, active_strat.get("timeframe", "15m") if active_strat else "15m")
        style = _extract_style(message)
        sl_val = _extract_pct_after(message, ("stop loss", "sl", "وقف الخسارة", "وقف خسارة", "الوقف"))
        tp_val = _extract_pct_after(message, ("take profit", "tp", "جني الربح", "الهدف", "هدف"))

        want_create = any(
            k in lower
            for k in ("create", "new strategy", "build strategy", "انشئ", "أنشئ", "اصنع", "اضف استراتيجية", "أضف استراتيجية", "بناء استراتيجية", "استراتيجية جديدة")
        )
        want_modify = (
            not want_create
            and any(k in lower for k in ("modify", "update strategy", "change stop", "عدل", "تعديل", "تحديث", "غير وقف", "غير الهدف"))
        )
        want_optimize = any(
            k in lower
            for k in ("walk-forward", "walk forward", "optimize", "best params", "تحسين", "ووك فورورد", "افضل اعدادات", "أفضل إعدادات", "طور")
        )
        want_backtest = any(
            k in lower
            for k in ("backtest", "run test", "simulate", "باك تيست", "باك-تيست", "اختبار", "اختبر", "جرب")
        )
        want_signals = any(
            k in lower
            for k in ("signal", "evaluate", "entry now", "اشارات", "إشارات", "فحص الدخول", "فرصة")
        )
        want_paper = any(
            k in lower
            for k in ("paper buy", "paper sell", "place order", "buy paper", "sell paper", "شراء ورقي", "بيع ورقي", "نفذ ورقي", "صفقة ورقية", "اشتر ")
        )
        want_risk = any(
            k in lower
            for k in ("risk profile", "risk per trade", "max risk", "اضبط المخاطر", "تعديل المخاطر", "حد المخاطرة", "إدارة المخاطر")
        )
        want_market = any(
            k in lower
            for k in ("market", "regime", "breadth", "سوق", "وضع السوق", "تحليل السوق", "اتجاه السوق")
        )

        actions: list[dict[str, Any]] = []
        lines: list[str] = []
        target_strat_id = active_strat["id"] if active_strat else None

        # Match explicit strategy name mention if user mentioned another strategy
        for s in strategies:
            if s["name"].lower() in lower:
                target_strat_id = s["id"]
                break

        if want_create:
            create_args: dict[str, Any] = {
                "name": f"AI {style.replace('_', ' ').title()} ({symbol} {timeframe})",
                "symbol": symbol,
                "timeframe": timeframe,
                "style": style,
                "stop_loss_pct": sl_val or 1.5,
                "take_profit_pct": tp_val or 3.5,
            }
            res = tool_executor("create_strategy", create_args)
            actions.append(res)
            if res.get("ok"):
                target_strat_id = res["data"]["strategy_id"]
                if is_ar:
                    lines.append(
                        f"• تم إنشاء الاستراتيجية **{res['data']['name']}** بـ {res['data']['indicator_count']} مؤشرات "
                        f"على `{symbol}` إطار `{timeframe}` (SL `{create_args['stop_loss_pct']}%` / TP `{create_args['take_profit_pct']}%`)."
                    )
                else:
                    lines.append(
                        f"• Created strategy **{res['data']['name']}** with {res['data']['indicator_count']} indicators on `{symbol}` `{timeframe}`."
                    )

        if want_modify and target_strat_id:
            mod_args: dict[str, Any] = {
                "strategy_id": target_strat_id,
                "change_note": "Updated via AI Trading Copilot discussion",
            }
            if sl_val is not None:
                mod_args["stop_loss_pct"] = sl_val
            if tp_val is not None:
                mod_args["take_profit_pct"] = tp_val
            if timeframe and any(tf.lower() in lower for tf in _TIMEFRAMES):
                mod_args["timeframe"] = timeframe
            if any(coin in message.upper() for coin in _KNOWN_COINS):
                mod_args["symbol"] = symbol
            res = tool_executor("modify_strategy", mod_args)
            actions.append(res)
            if res.get("ok"):
                d = res["data"]
                if is_ar:
                    lines.append(
                        f"• تم حفظ نسخة جديدة **v{d['version_no']}** من `{d['strategy_name']}` "
                        f"(SL `{d['stop_loss_pct']}%` / TP `{d['take_profit_pct']}%`)."
                    )
                else:
                    lines.append(
                        f"• Saved immutable version **v{d['version_no']}** of `{d['strategy_name']}` "
                        f"(SL `{d['stop_loss_pct']}%` / TP `{d['take_profit_pct']}%`)."
                    )

        if want_backtest or want_create:
            bt_res = tool_executor(
                "run_backtest",
                {
                    "strategy_id": target_strat_id,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "bars": 300,
                    "initial_capital_usdt": 10000.0,
                },
            )
            actions.append(bt_res)
            if bt_res.get("ok"):
                m = bt_res["data"]["metrics"]
                if is_ar:
                    lines.append(
                        f"• نتائج الباك-تيست على `{bt_res['data']['symbol']}` ({bt_res['data']['timeframe']}): "
                        f"العائد **{m['total_return_pct']:.2f}%** | الصفقات **{m['total_trades']}** | "
                        f"نسبة الفوز **{m['win_rate_pct']:.1f}%** | أقصى تراجع **-{m['max_drawdown_pct']:.2f}%** | "
                        f"Sharpe `{m['sharpe_ratio']:.2f}` | Factor `{m['profit_factor']:.2f}`."
                    )
                else:
                    lines.append(
                        f"• Backtest `{bt_res['data']['symbol']}` ({bt_res['data']['timeframe']}): Return **{m['total_return_pct']:.2f}%**, "
                        f"Trades **{m['total_trades']}**, Win Rate **{m['win_rate_pct']:.1f}%**, Max DD **-{m['max_drawdown_pct']:.2f}%**, "
                        f"Sharpe `{m['sharpe_ratio']:.2f}`."
                    )

        if want_optimize:
            opt_res = tool_executor(
                "run_walk_forward",
                {
                    "strategy_id": target_strat_id,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "bars": 300,
                    "apply_best_params": True,
                },
            )
            actions.append(opt_res)
            if opt_res.get("ok"):
                d = opt_res["data"]
                bp = d["best_params"]
                oos = d["out_of_sample_metrics"]
                if is_ar:
                    overfit_txt = "تنبيه فرط تخصيص (Overfitting)" if d["overfitting_warning"] else "النتائج متماسكة خارج العينة"
                    lines.append(
                        f"• تحسين Walk-Forward (70% IS / 30% OOS): أفضل SL/TP = `{bp['stop_loss_pct']}% / {bp['take_profit_pct']}%` "
                        f"— عائد OOS **{oos['total_return_pct']:.2f}%** ({overfit_txt})."
                    )
                else:
                    lines.append(
                        f"• Walk-Forward Best SL/TP: `{bp['stop_loss_pct']}% / {bp['take_profit_pct']}%`, "
                        f"OOS Return **{oos['total_return_pct']:.2f}%**."
                    )

        if want_signals:
            sig_res = tool_executor(
                "evaluate_signals",
                {"strategy_id": target_strat_id, "symbol": symbol, "timeframe": timeframe},
            )
            actions.append(sig_res)
            if sig_res.get("ok"):
                d = sig_res["data"]
                if is_ar:
                    lines.append(
                        f"• فحص الإشارات الحية على `{d['symbol']}` ({d['timeframe']}): "
                        f"درجة التوافق الحالية **{d['latest_confluence']:.2f}**، إشارات دخول `{d['entry_count']}` وخروج `{d['exit_count']}`."
                    )
                else:
                    lines.append(
                        f"• Live signals `{d['symbol']}` ({d['timeframe']}): confluence **{d['latest_confluence']:.2f}**, "
                        f"{d['entry_count']} entries, {d['exit_count']} exits."
                    )

        if want_paper:
            side = "sell" if any(k in lower for k in ("sell", "بيع")) else "buy"
            qty_m = re.search(r"(?:buy|sell|اشتر|شراء|بيع|كمية|qty)[^\d]{0,20}(\d+(?:\.\d+)?)\b", lower)
            if qty_m:
                qty = float(qty_m.group(1))
            else:
                qty = 0.01
            p_res = tool_executor("execute_paper_order", {"symbol": symbol, "side": side, "qty": qty})
            actions.append(p_res)
            if p_res.get("ok"):
                d = p_res["data"]
                if is_ar:
                    lines.append(
                        f"• تم تنفيذ أمر ورقي ({d['side'].upper()}) لـ `{d['qty']} {d['symbol']}` بسعر `{d['price']}` (حساب معزول تماماً)."
                    )
                else:
                    lines.append(
                        f"• Executed Paper {d['side'].upper()} `{d['qty']} {d['symbol']}` @ `{d['price']}`."
                    )

        if want_risk:
            r_args: dict[str, Any] = {}
            risk_pt = _extract_pct_after(message, ("risk per trade", "مخاطرة الصفقة", "مخاطرة"))
            daily_l = _extract_pct_after(message, ("daily", "يومي", "اليومية"))
            dd_l = _extract_pct_after(message, ("drawdown", "تراجع"))
            if risk_pt is not None:
                r_args["max_risk_per_trade_pct"] = risk_pt
            if daily_l is not None:
                r_args["max_daily_loss_pct"] = daily_l
            if dd_l is not None:
                r_args["max_drawdown_pct"] = dd_l
            if not r_args:
                r_args["max_risk_per_trade_pct"] = 1.5
            r_res = tool_executor("update_risk_profile", r_args)
            actions.append(r_res)
            if r_res.get("ok"):
                rp = r_res["data"]
                if is_ar:
                    lines.append(
                        f"• تم تحديث ملف المخاطر: مخاطرة/صفقة `{rp['max_risk_per_trade_pct']}%` | حد يومي `{rp['max_daily_loss_pct']}%` | أقصى تراجع `{rp['max_drawdown_pct']}%`."
                    )
                else:
                    lines.append(
                        f"• Updated Risk Profile: {rp['max_risk_per_trade_pct']}% per trade, {rp['max_daily_loss_pct']}% daily loss limit."
                    )

        if want_market or not actions:
            m_res = tool_executor("get_market_intelligence", {})
            actions.append(m_res)
            if m_res.get("ok"):
                mi = m_res["data"]
                if is_ar:
                    lines.append(
                        f"• حالة السوق الحي على MEXC: **{mi['regime']}** (اتساع السوق `{mi['breadth_pct']}%`، متوسط التغير `{mi['avg_change_pct']}%`)."
                    )
                else:
                    lines.append(
                        f"• Live MEXC Market Regime: **{mi['regime']}** (Breadth `{mi['breadth_pct']}%`, Avg 24h `{mi['avg_change_pct']}%`)."
                    )

        if not want_create and not want_backtest and not want_optimize and not want_modify and not want_signals and not want_paper and not want_risk:
            # Discussion / strategic critique using existing app state
            recent_bts = app_state.get("recent_backtests", [])
            paper_acc = app_state.get("paper_account", {})
            if is_ar:
                if strategies:
                    s_summary = "، ".join(f"`{s['name']}` ({s['symbol']} · {s['timeframe']} · SL {s['stop_loss_pct']}%)" for s in strategies[:3])
                    lines.append(f"• الاستراتيجيات النشطة لديك الآن ({len(strategies)}): {s_summary}.")
                if recent_bts:
                    top = recent_bts[0]
                    lines.append(
                        f"• آخر باك-تيست مسجل (`{top['strategy_name']}` على `{top['symbol']}`): "
                        f"العائد `{top['total_return_pct']:.2f}%`، Win Rate `{top['win_rate_pct']:.1f}%`، Max DD `-{top['max_drawdown_pct']:.2f}%`."
                    )
                lines.append(
                    f"• رصيد المحفظة الورقية المعزولة: **${float(paper_acc.get('total_equity_usdt', 10000.0)):,.2f}**."
                )
                lines.append(
                    "• يمكنني الآن التناقش معك أو التنفيذ مباشرة: اطلب مني مثلاً *إنشاء استراتيجية جديدة + تشغيل باك-تيست*، "
                    "أو *تشغيل Walk-Forward Optimization*، أو *تعديل وقف الخسارة*، أو *فتح صفقة ورقية للاختبار*."
                )
            else:
                if strategies:
                    lines.append(f"• Active strategies ({len(strategies)}): " + ", ".join(s["name"] for s in strategies[:3]))
                if recent_bts:
                    top = recent_bts[0]
                    lines.append(
                        f"• Latest backtest (`{top['strategy_name']}`): {top['total_return_pct']:.2f}% return, {top['win_rate_pct']:.1f}% win rate."
                    )
                lines.append(
                    "• Tell me to create/modify strategies, run backtests, run Walk-Forward optimization, evaluate signals, or place paper orders."
                )

        reply = "\n".join(lines)
        return {
            "reply": reply,
            "provider_used": "builtin:apex-quant-copilot-v1",
            "tool_actions": actions,
            "quick_prompts": self._suggest_quick_prompts(message, "ar" if is_ar else "en", actions),
            "fallback_warning": None,
        }

    def _suggest_quick_prompts(
        self,
        last_message: str,
        lang: str,
        actions: list[dict[str, Any]],
    ) -> list[str]:
        if lang == "ar" or _has_arabic(last_message):
            return [
                "أنشئ استراتيجية زخم على SOL/USDT 15m وشغل باك تيست",
                "اعمل Walk-Forward Optimization وحسن الإعدادات",
                "افحص الإشارات الحية على ETH/USDT الآن",
                "عدل وقف الخسارة إلى 1.2% والهدف إلى 4.0% ثم اختبر",
            ]
        return [
            "Create a SOL/USDT 15m momentum strategy and run backtest",
            "Run Walk-Forward Optimization and apply best parameters",
            "Evaluate live signals on ETH/USDT 15m",
            "Tighten stop loss to 1.2% and re-test",
        ]
