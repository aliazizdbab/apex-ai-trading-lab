from __future__ import annotations

import copy
from datetime import timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.copilot import PROVIDER_CATALOG, CopilotAgent
from ai.provider import AIProviderManager
from app.api.backtest_replay import (
    BacktestRunRequest,
    optimize_backtest_endpoint,
    run_backtest_endpoint,
)
from app.api.router import _vault, get_optional_session_and_user
from app.api.strategies import (
    StrategyCreateRequest,
    StrategyEvaluateRequest,
    StrategyNewVersionRequest,
    StrategyStatusRequest,
    create_strategy,
    create_strategy_version,
    ensure_default_strategies,
    evaluate_strategy_endpoint,
    list_strategies,
    update_strategy_status,
)
from app.api.trading_risk import (
    OrderSubmitRequest,
    RiskProfileUpdateRequest,
    get_paper_overview,
    get_risk_profile,
    submit_paper_order,
    update_risk_profile,
)
from app.core.crypto import SecretVault, mask_secret
from app.db.models import (
    AiConversation,
    AiCopilotConfig,
    BacktestJob,
    Strategy,
    StrategyVersion,
    User,
    UserSession,
    utcnow,
)
from app.db.session import get_db
from app.services.audit import append_audit_log
from app.services.market_data import DEFAULT_SPOT_SYMBOLS, TIMEFRAME_SECONDS
from app.services.mexc_provider import get_mexc_client
from engine.strategy.evaluator import validate_strategy_definition
from exchanges.mexc.market_client import MexcMarketDataClient

copilot_router = APIRouter(prefix="/api/v1/ai/copilot")
_copilot = CopilotAgent()
_ai_manager = AIProviderManager()


def _iso(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _ensure_copilot_config(db: Session) -> AiCopilotConfig:
    cfg = db.execute(select(AiCopilotConfig).limit(1)).scalar_one_or_none()
    if cfg is not None:
        return cfg
    cfg = AiCopilotConfig(
        provider="builtin",
        model_name=PROVIDER_CATALOG["builtin"]["default_model"],
        base_url="",
        autonomy_level="full_copilot",
        system_instructions="",
        enabled=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def _serialize_config(cfg: AiCopilotConfig) -> dict[str, Any]:
    return {
        "id": cfg.id,
        "provider": cfg.provider,
        "model_name": cfg.model_name,
        "base_url": cfg.base_url or PROVIDER_CATALOG.get(cfg.provider, {}).get("base_url", ""),
        "has_api_key": bool(cfg.api_key_encrypted),
        "api_key_masked": cfg.api_key_masked or "",
        "autonomy_level": cfg.autonomy_level,
        "system_instructions": cfg.system_instructions,
        "enabled": cfg.enabled,
        "updated_at": _iso(cfg.updated_at),
        "providers": [
            {
                "id": k,
                "label": v["label"],
                "default_model": v["default_model"],
                "default_base_url": v["base_url"],
            }
            for k, v in PROVIDER_CATALOG.items()
        ],
    }


def _decrypt_cfg_key(cfg: AiCopilotConfig, vault: SecretVault) -> str | None:
    if not cfg.api_key_encrypted:
        return None
    try:
        return vault.decrypt(cfg.api_key_encrypted)
    except Exception:
        return None


def _resolve_strategy(db: Session, strategy_id: str | None) -> tuple[Strategy, StrategyVersion]:
    ensure_default_strategies(db)
    strat = None
    if strategy_id:
        strat = db.execute(select(Strategy).where(Strategy.id == strategy_id)).scalar_one_or_none()
    if strat is None:
        strat = db.execute(select(Strategy).order_by(Strategy.updated_at.desc()).limit(1)).scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail="No strategies available")
    ver = db.execute(select(StrategyVersion).where(StrategyVersion.id == strat.current_version_id)).scalar_one_or_none()
    if ver is None:
        ver = (
            db.execute(
                select(StrategyVersion)
                .where(StrategyVersion.strategy_id == strat.id)
                .order_by(StrategyVersion.version_no.desc())
                .limit(1)
            ).scalar_one_or_none()
        )
    if ver is None:
        raise HTTPException(status_code=404, detail="Strategy version not found")
    return strat, ver


def _build_app_state(db: Session, client: MexcMarketDataClient, active_page: str, active_strategy_id: str | None) -> dict[str, Any]:
    ensure_default_strategies(db)
    strats = list_strategies(db=db)["items"]
    bt_rows = db.execute(select(BacktestJob).order_by(BacktestJob.created_at.desc()).limit(10)).scalars().all()
    ver_to_strat: dict[str, str] = {}
    for s in strats:
        for v in s.get("versions") or []:
            ver_to_strat[v["id"]] = s["name"]

    paper = get_paper_overview(db=db, client=client)
    risk = get_risk_profile(db=db)

    # Place requested active_strategy_id first so tools default to what the owner is viewing
    ordered_strats = sorted(strats, key=lambda item: 0 if item["id"] == active_strategy_id else 1)

    return {
        "active_page": active_page,
        "strategies": [
            {
                "id": s["id"],
                "name": s["name"],
                "status": s["status"],
                "current_version_id": s["current_version_id"],
                "symbol": (s.get("current_version") or {}).get("definition", {}).get("symbol", "BTC/USDT"),
                "timeframe": (s.get("current_version") or {}).get("definition", {}).get("timeframe", "15m"),
                "stop_loss_pct": (s.get("current_version") or {}).get("definition", {}).get("stop_loss_pct", 1.5),
                "take_profit_pct": (s.get("current_version") or {}).get("definition", {}).get("take_profit_pct", 3.5),
            }
            for s in ordered_strats
        ],
        "recent_backtests": [
            {
                "id": b.id,
                "strategy_name": ver_to_strat.get(b.strategy_version_id, "Strategy"),
                "symbol": b.symbol,
                "timeframe": b.timeframe,
                "total_return_pct": (b.metrics_json or {}).get("total_return_pct", 0.0),
                "win_rate_pct": (b.metrics_json or {}).get("win_rate_pct", 0.0),
                "max_drawdown_pct": (b.metrics_json or {}).get("max_drawdown_pct", 0.0),
                "sharpe_ratio": (b.metrics_json or {}).get("sharpe_ratio", 0.0),
            }
            for b in bt_rows
        ],
        "paper_account": paper["account"],
        "risk_profile": risk,
    }


def _make_tool_executor(
    *,
    db: Session,
    client: MexcMarketDataClient,
    ctx: tuple[UserSession | None, User | None],
    autonomy_level: str,
    default_strategy_id: str | None,
):
    session_ctx: dict[str, str | None] = {"strategy_id": default_strategy_id}

    def execute_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if tool_name == "create_strategy":
                symbol = str(args.get("symbol") or "BTC/USDT").strip().upper()
                timeframe = str(args.get("timeframe") or "15m").strip()
                if timeframe not in TIMEFRAME_SECONDS:
                    timeframe = "15m"
                style = str(args.get("style") or "momentum")
                prompt_hint = f"{style} {symbol} {timeframe}"
                generated = _ai_manager.generate_strategy_draft(
                    prompt=prompt_hint, symbol=symbol, timeframe=timeframe, gemini_configured=True
                )
                defn = copy.deepcopy(generated["definition"])
                if args.get("stop_loss_pct") is not None:
                    defn["stop_loss_pct"] = max(0.2, min(25.0, float(args["stop_loss_pct"])))
                if args.get("take_profit_pct") is not None:
                    defn["take_profit_pct"] = max(0.4, min(100.0, float(args["take_profit_pct"])))
                defn = validate_strategy_definition(defn)
                custom_name = str(args.get("name") or generated["name"])[:140]
                created = create_strategy(
                    StrategyCreateRequest(
                        name=custom_name,
                        description=generated["description"],
                        status="Backtesting" if autonomy_level == "full_copilot" else "Draft",
                        definition=defn,
                        change_note="Synthesized via APEX AI Copilot",
                    ),
                    db=db,
                    ctx=ctx,
                )
                session_ctx["strategy_id"] = created["id"]
                return {
                    "tool": "create_strategy",
                    "ok": True,
                    "title": f"Strategy Created: {created['name']}",
                    "route": "/strategy-composer",
                    "data": {
                        "strategy_id": created["id"],
                        "strategy_version_id": created["current_version_id"],
                        "name": created["name"],
                        "symbol": defn["symbol"],
                        "timeframe": defn["timeframe"],
                        "stop_loss_pct": defn["stop_loss_pct"],
                        "take_profit_pct": defn["take_profit_pct"],
                        "indicator_count": len(defn["indicators"]),
                        "status": created["status"],
                    },
                }

            if tool_name == "modify_strategy":
                target_id = args.get("strategy_id") or session_ctx["strategy_id"]
                strat, ver = _resolve_strategy(db, str(target_id) if target_id else None)
                defn = copy.deepcopy(ver.definition_json)
                if args.get("stop_loss_pct") is not None:
                    defn["stop_loss_pct"] = max(0.2, min(25.0, float(args["stop_loss_pct"])))
                if args.get("take_profit_pct") is not None:
                    defn["take_profit_pct"] = max(0.4, min(100.0, float(args["take_profit_pct"])))
                if args.get("timeframe") and str(args["timeframe"]) in TIMEFRAME_SECONDS:
                    defn["timeframe"] = str(args["timeframe"])
                if args.get("symbol"):
                    defn["symbol"] = str(args["symbol"]).strip().upper()
                defn = validate_strategy_definition(defn)
                note = str(args.get("change_note") or "Adjusted parameters via AI Copilot")[:255]
                updated = create_strategy_version(
                    strat.id,
                    StrategyNewVersionRequest(definition=defn, change_note=note),
                    db=db,
                    ctx=ctx,
                )
                if args.get("status"):
                    updated = update_strategy_status(
                        strat.id, StrategyStatusRequest(status=str(args["status"])), db=db
                    )
                session_ctx["strategy_id"] = strat.id
                return {
                    "tool": "modify_strategy",
                    "ok": True,
                    "title": f"Updated {updated['name']} (v{updated['current_version']['version_no']})",
                    "route": "/strategy-composer",
                    "data": {
                        "strategy_id": strat.id,
                        "strategy_name": updated["name"],
                        "version_no": updated["current_version"]["version_no"],
                        "symbol": defn["symbol"],
                        "timeframe": defn["timeframe"],
                        "stop_loss_pct": defn["stop_loss_pct"],
                        "take_profit_pct": defn["take_profit_pct"],
                        "status": updated["status"],
                    },
                }

            if tool_name == "run_backtest":
                target_id = args.get("strategy_id") or session_ctx["strategy_id"]
                strat, ver = _resolve_strategy(db, str(target_id) if target_id else None)
                sym = str(args.get("symbol") or ver.definition_json.get("symbol", "BTC/USDT")).upper()
                tf = str(args.get("timeframe") or ver.definition_json.get("timeframe", "15m"))
                if tf not in TIMEFRAME_SECONDS:
                    tf = "15m"
                bars = max(80, min(1000, int(args.get("bars") or 300)))
                cap = max(100.0, float(args.get("initial_capital_usdt") or 10000.0))
                bt = run_backtest_endpoint(
                    BacktestRunRequest(
                        strategy_version_id=ver.id,
                        symbol=sym,
                        timeframe=tf,
                        bars=bars,
                        initial_capital_usdt=cap,
                    ),
                    db=db,
                    client=client,
                )
                session_ctx["strategy_id"] = strat.id
                return {
                    "tool": "run_backtest",
                    "ok": True,
                    "title": f"Backtest: {strat.name} ({bt['symbol']} {bt['timeframe']})",
                    "route": "/backtesting",
                    "data": {
                        "job_id": bt["id"],
                        "strategy_id": strat.id,
                        "strategy_name": strat.name,
                        "symbol": bt["symbol"],
                        "timeframe": bt["timeframe"],
                        "metrics": bt["metrics"],
                        "vectorized_parity": bt["vectorized_parity"],
                    },
                }

            if tool_name == "run_walk_forward":
                target_id = args.get("strategy_id") or session_ctx["strategy_id"]
                strat, ver = _resolve_strategy(db, str(target_id) if target_id else None)
                sym = str(args.get("symbol") or ver.definition_json.get("symbol", "BTC/USDT")).upper()
                tf = str(args.get("timeframe") or ver.definition_json.get("timeframe", "15m"))
                if tf not in TIMEFRAME_SECONDS:
                    tf = "15m"
                bars = max(120, min(1000, int(args.get("bars") or 300)))
                opt = optimize_backtest_endpoint(
                    BacktestRunRequest(strategy_version_id=ver.id, symbol=sym, timeframe=tf, bars=bars),
                    db=db,
                    client=client,
                )
                applied_ver = None
                if bool(args.get("apply_best_params", True)):
                    new_defn = copy.deepcopy(ver.definition_json)
                    new_defn["stop_loss_pct"] = opt["best_params"]["stop_loss_pct"]
                    new_defn["take_profit_pct"] = opt["best_params"]["take_profit_pct"]
                    upd = create_strategy_version(
                        strat.id,
                        StrategyNewVersionRequest(
                            definition=validate_strategy_definition(new_defn),
                            change_note="Applied Walk-Forward best SL/TP via AI Copilot",
                        ),
                        db=db,
                        ctx=ctx,
                    )
                    applied_ver = upd["current_version"]["version_no"]
                return {
                    "tool": "run_walk_forward",
                    "ok": True,
                    "title": f"Walk-Forward 70/30: {strat.name} ({sym} {tf})",
                    "route": "/optimization",
                    "data": {
                        "strategy_id": strat.id,
                        "applied_version_no": applied_ver,
                        "best_params": opt["best_params"],
                        "in_sample_metrics": opt["in_sample_metrics"],
                        "out_of_sample_metrics": opt["out_of_sample_metrics"],
                        "overfitting_warning": opt["overfitting_warning"],
                        "overfitting_reason": opt["overfitting_reason"],
                    },
                }

            if tool_name == "evaluate_signals":
                target_id = args.get("strategy_id") or session_ctx["strategy_id"]
                _, ver = _resolve_strategy(db, str(target_id) if target_id else None)
                sym = str(args.get("symbol") or ver.definition_json.get("symbol", "BTC/USDT")).upper()
                tf = str(args.get("timeframe") or ver.definition_json.get("timeframe", "15m"))
                if tf not in TIMEFRAME_SECONDS:
                    tf = "15m"
                ev = evaluate_strategy_endpoint(
                    StrategyEvaluateRequest(strategy_version_id=ver.id, symbol=sym, timeframe=tf, limit=250),
                    db=db,
                    client=client,
                )
                return {
                    "tool": "evaluate_signals",
                    "ok": True,
                    "title": f"Live Signals: {sym} ({tf})",
                    "route": "/terminal",
                    "data": ev,
                }

            if tool_name == "execute_paper_order":
                if autonomy_level == "research_only":
                    return {
                        "tool": "execute_paper_order",
                        "ok": False,
                        "title": "Autonomy Gate: Research Only",
                        "route": "/paper-trading",
                        "error": "Switch Copilot Autonomy to 'Research + Paper Trading' or 'Full Quant Copilot' to place paper orders.",
                    }
                sym = str(args.get("symbol") or "BTC/USDT").upper()
                side_raw = str(args.get("side") or "buy").lower()
                side: Literal["buy", "sell"] = "sell" if side_raw == "sell" else "buy"
                qty = max(0.0001, float(args.get("qty") or 0.01))
                filled = submit_paper_order(
                    OrderSubmitRequest(symbol=sym, side=side, order_type="MARKET", qty=qty),
                    db=db,
                    client=client,
                )
                return {
                    "tool": "execute_paper_order",
                    "ok": True,
                    "title": f"Paper {filled['side'].upper()} {filled['qty']} {filled['symbol']}",
                    "route": "/paper-trading",
                    "data": filled,
                }

            if tool_name == "update_risk_profile":
                if autonomy_level != "full_copilot":
                    return {
                        "tool": "update_risk_profile",
                        "ok": False,
                        "title": "Autonomy Gate: Full Copilot Required",
                        "route": "/risk",
                        "error": "Switch Copilot Autonomy to 'Full Quant Copilot' to modify RiskEngine thresholds.",
                    }
                curr = get_risk_profile(db=db)
                rp = update_risk_profile(
                    RiskProfileUpdateRequest(
                        max_risk_per_trade_pct=float(args.get("max_risk_per_trade_pct") or curr["max_risk_per_trade_pct"]),
                        max_daily_loss_pct=float(args.get("max_daily_loss_pct") or curr["max_daily_loss_pct"]),
                        max_weekly_loss_pct=float(curr["max_weekly_loss_pct"]),
                        max_drawdown_pct=float(args.get("max_drawdown_pct") or curr["max_drawdown_pct"]),
                        max_open_positions=int(args.get("max_open_positions") or curr["max_open_positions"]),
                        max_asset_exposure_pct=float(curr["max_asset_exposure_pct"]),
                        cooldown_minutes=int(curr["cooldown_minutes"]),
                    ),
                    db=db,
                    ctx=ctx,
                )
                return {
                    "tool": "update_risk_profile",
                    "ok": True,
                    "title": "Risk Profile Updated",
                    "route": "/risk",
                    "data": rp,
                }

            if tool_name == "get_market_intelligence":
                tickers = client.get_24h_tickers(DEFAULT_SPOT_SYMBOLS)
                intel = _ai_manager.build_market_intelligence(tickers)
                return {
                    "tool": "get_market_intelligence",
                    "ok": True,
                    "title": f"Market Regime: {intel['regime']}",
                    "route": "/market-intelligence",
                    "data": intel,
                }

            return {"tool": tool_name, "ok": False, "title": tool_name, "error": f"Unknown tool '{tool_name}'"}
        except HTTPException as exc:
            return {"tool": tool_name, "ok": False, "title": tool_name, "error": str(exc.detail)}
        except Exception as exc:
            return {"tool": tool_name, "ok": False, "title": tool_name, "error": str(exc)}

    return execute_tool


class CopilotConfigUpdateRequest(BaseModel):
    provider: Literal["builtin", "gemini", "openai", "anthropic", "deepseek", "openrouter", "custom"] = "builtin"
    model_name: str = Field(default="apex-quant-copilot-v1", min_length=1, max_length=120)
    base_url: str | None = Field(default="", max_length=255)
    api_key: str | None = Field(default=None, max_length=512)
    clear_api_key: bool = False
    autonomy_level: Literal["full_copilot", "research_and_paper", "research_only"] = "full_copilot"
    system_instructions: str = Field(default="", max_length=4000)
    enabled: bool = True


class CopilotTestRequest(BaseModel):
    provider: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class CopilotConversationCreateRequest(BaseModel):
    topic: str = Field(default="New Quant Strategy Session", min_length=1, max_length=140)


class CopilotChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=6000)
    active_page: str = Field(default="/", max_length=120)
    active_strategy_id: str | None = None
    language_hint: str = Field(default="en", max_length=16)


@copilot_router.get("/config")
def get_copilot_config(db: Session = Depends(get_db)) -> dict[str, Any]:
    cfg = _ensure_copilot_config(db)
    return _serialize_config(cfg)


@copilot_router.put("/config")
def update_copilot_config(
    payload: CopilotConfigUpdateRequest,
    db: Session = Depends(get_db),
    vault: SecretVault = Depends(_vault),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    cfg = _ensure_copilot_config(db)
    cfg.provider = payload.provider
    cfg.model_name = payload.model_name.strip() or PROVIDER_CATALOG[payload.provider]["default_model"]
    cfg.base_url = (payload.base_url or "").strip()
    cfg.autonomy_level = payload.autonomy_level
    cfg.system_instructions = payload.system_instructions.strip()
    cfg.enabled = payload.enabled

    if payload.clear_api_key:
        cfg.api_key_encrypted = None
        cfg.api_key_masked = None
    elif payload.api_key and payload.api_key.strip():
        raw_key = payload.api_key.strip()
        cfg.api_key_encrypted = vault.encrypt(raw_key)
        cfg.api_key_masked = mask_secret(raw_key)

    cfg.updated_at = utcnow()
    _, current_user = ctx
    if current_user is not None:
        append_audit_log(
            db,
            actor=current_user.email,
            action="ai.copilot_config_updated",
            entity=f"ai_copilot_config:{cfg.id}",
            payload={
                "provider": cfg.provider,
                "model_name": cfg.model_name,
                "autonomy_level": cfg.autonomy_level,
                "has_api_key": bool(cfg.api_key_encrypted),
            },
            owner_id=current_user.id,
        )
    db.commit()
    db.refresh(cfg)
    return _serialize_config(cfg)


@copilot_router.post("/test")
def test_copilot_connection(
    payload: CopilotTestRequest,
    db: Session = Depends(get_db),
    vault: SecretVault = Depends(_vault),
) -> dict[str, Any]:
    cfg = _ensure_copilot_config(db)
    provider = (payload.provider or cfg.provider).strip()
    model_name = (payload.model_name or cfg.model_name).strip()
    base_url = payload.base_url if payload.base_url is not None else cfg.base_url
    raw_key = payload.api_key.strip() if (payload.api_key and payload.api_key.strip()) else _decrypt_cfg_key(cfg, vault)
    return _copilot.test_connection(
        provider=provider,
        model_name=model_name,
        api_key=raw_key,
        base_url=base_url,
    )


@copilot_router.get("/conversations")
def list_copilot_conversations(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = (
        db.execute(select(AiConversation).order_by(AiConversation.created_at.desc()).limit(25))
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": c.id,
                "provider": c.provider,
                "topic": c.topic,
                "messages": c.messages_json or [],
                "created_at": _iso(c.created_at),
            }
            for c in rows
        ]
    }


@copilot_router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_copilot_conversation(
    payload: CopilotConversationCreateRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    cfg = _ensure_copilot_config(db)
    _, current_user = ctx
    conv = AiConversation(
        owner_id=current_user.id if current_user else None,
        provider=f"{cfg.provider}:{cfg.model_name}",
        topic=payload.topic.strip(),
        messages_json=[],
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {
        "id": conv.id,
        "provider": conv.provider,
        "topic": conv.topic,
        "messages": [],
        "created_at": _iso(conv.created_at),
    }


@copilot_router.delete("/conversations/{conversation_id}")
def delete_copilot_conversation(conversation_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    conv = db.execute(select(AiConversation).where(AiConversation.id == conversation_id)).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"ok": True, "id": conversation_id}


@copilot_router.post("/chat")
def copilot_chat_turn(
    payload: CopilotChatRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
    vault: SecretVault = Depends(_vault),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    cfg = _ensure_copilot_config(db)
    _, current_user = ctx

    conv = None
    if payload.conversation_id:
        conv = db.execute(select(AiConversation).where(AiConversation.id == payload.conversation_id)).scalar_one_or_none()
    if conv is None:
        topic_preview = payload.message.strip().splitlines()[0][:64] or "Quant Strategy Discussion"
        conv = AiConversation(
            owner_id=current_user.id if current_user else None,
            provider=f"{cfg.provider}:{cfg.model_name}",
            topic=topic_preview,
            messages_json=[],
        )
        db.add(conv)
        db.flush()

    app_state = _build_app_state(db, client, payload.active_page, payload.active_strategy_id)
    executor = _make_tool_executor(
        db=db,
        client=client,
        ctx=ctx,
        autonomy_level=cfg.autonomy_level,
        default_strategy_id=payload.active_strategy_id,
    )
    api_key = _decrypt_cfg_key(cfg, vault)

    result = _copilot.run_turn(
        message=payload.message,
        history=list(conv.messages_json or []),
        app_state=app_state,
        tool_executor=executor,
        provider=cfg.provider,
        model_name=cfg.model_name,
        api_key=api_key,
        base_url=cfg.base_url,
        autonomy_level=cfg.autonomy_level,
        system_instructions=cfg.system_instructions,
        language_hint=payload.language_hint,
    )

    now_iso = _iso(utcnow())
    msgs = list(conv.messages_json or [])
    msgs.append({"role": "user", "content": payload.message, "created_at": now_iso})
    msgs.append(
        {
            "role": "assistant",
            "content": result["reply"],
            "provider_used": result["provider_used"],
            "tool_actions": result["tool_actions"],
            "fallback_warning": result["fallback_warning"],
            "created_at": now_iso,
        }
    )
    conv.messages_json = msgs
    conv.provider = result["provider_used"]
    db.commit()

    return {
        "conversation_id": conv.id,
        "topic": conv.topic,
        "reply": result["reply"],
        "provider_used": result["provider_used"],
        "tool_actions": result["tool_actions"],
        "quick_prompts": result["quick_prompts"],
        "fallback_warning": result["fallback_warning"],
        "messages": msgs,
    }
