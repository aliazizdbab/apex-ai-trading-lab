from __future__ import annotations

from datetime import timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.provider import AIProviderManager
from app.api.router import get_optional_session_and_user
from app.api.strategies import ensure_default_strategies
from app.db.models import (
    AiConversation,
    AiSuggestion,
    ApiCredential,
    BacktestJob,
    PineScript,
    PineScriptVersion,
    Strategy,
    StrategyVersion,
    User,
    UserSession,
    utcnow,
)
from app.db.session import get_db
from app.services.audit import append_audit_log
from app.services.market_data import DEFAULT_SPOT_SYMBOLS, TIMEFRAME_SECONDS, sync_and_get_candles
from app.services.mexc_provider import get_mexc_client
from engine.pine.engine import analyze_pine_script, execute_pine_script
from engine.strategy.evaluator import compute_definition_hash
from exchanges.mexc.market_client import MexcApiError, MexcMarketDataClient

pine_ai_router = APIRouter(prefix="/api/v1")
_ai_manager = AIProviderManager()

_DEFAULT_PINE_SOURCE = """//@version=5
strategy("APEX EMA + RSI Momentum v5", overlay=true)
fastLen = input.int(9, title="Fast EMA Length", minval=2, maxval=100)
slowLen = input.int(21, title="Slow EMA Length", minval=5, maxval=200)
rsiLen = input.int(14, title="RSI Length", minval=2, maxval=100)

fastEma = ta.ema(close, fastLen)
slowEma = ta.ema(close, slowLen)
rsiVal = ta.rsi(close, rsiLen)

plot(fastEma, title="Fast EMA")
plot(slowEma, title="Slow EMA")

strategy.entry("Long", strategy.long, when=ta.crossover(fastEma, slowEma) and rsiVal > 45)
strategy.close("Long", when=ta.crossunder(fastEma, slowEma) or rsiVal > 75)
"""


def _iso(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def ensure_default_pine_scripts(db: Session) -> None:
    if db.execute(select(PineScript.id).limit(1)).scalar_one_or_none() is not None:
        return
    analysis = analyze_pine_script(_DEFAULT_PINE_SOURCE)
    script = PineScript(name=analysis["title"], script_type=analysis["script_type"])
    db.add(script)
    db.flush()
    ver = PineScriptVersion(
        script_id=script.id,
        version_no=1,
        source_code=_DEFAULT_PINE_SOURCE,
        pine_version=analysis["pine_version"],
        ast_json=analysis["ast"],
        compat_report_json={
            **analysis["compat_report"],
            "inputs": analysis["inputs"],
            "builtin_indicators": analysis["builtin_indicators"],
        },
        sha256=analysis["sha256"],
    )
    db.add(ver)
    db.flush()
    script.current_version_id = ver.id
    db.commit()


def _serialize_pine_script(db: Session, s: PineScript) -> dict[str, Any]:
    versions = (
        db.execute(
            select(PineScriptVersion)
            .where(PineScriptVersion.script_id == s.id)
            .order_by(PineScriptVersion.version_no.desc())
        )
        .scalars()
        .all()
    )
    curr = next((v for v in versions if v.id == s.current_version_id), versions[0] if versions else None)
    return {
        "id": s.id,
        "name": s.name,
        "script_type": s.script_type,
        "version_count": len(versions),
        "current_version": {
            "id": curr.id,
            "version_no": curr.version_no,
            "source_code": curr.source_code,
            "pine_version": curr.pine_version,
            "ast": curr.ast_json,
            "compat_report": curr.compat_report_json,
            "sha256": curr.sha256,
            "created_at": _iso(curr.created_at),
        }
        if curr
        else None,
        "created_at": _iso(s.created_at),
    }


class PineAnalyzeRequest(BaseModel):
    source_code: str = Field(min_length=5)


class PineSaveRequest(BaseModel):
    script_id: str | None = None
    name: str | None = None
    source_code: str = Field(min_length=5)


class PineExecuteRequest(BaseModel):
    source_code: str = Field(min_length=5)
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="15m", min_length=2, max_length=16)
    limit: int = Field(default=150, ge=30, le=500)
    input_overrides: dict[str, Any] = Field(default_factory=dict)


class AiStrategyBuilderRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1500)
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="15m", min_length=2, max_length=16)


class AiResearchRequest(BaseModel):
    backtest_job_id: str | None = None
    strategy_id: str | None = None
    prompt: str = Field(default="Analyze risk-adjusted return and propose safer parameters.", max_length=1000)


class AiDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]


@pine_ai_router.get("/pine/scripts")
def list_pine_scripts(db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_default_pine_scripts(db)
    rows = db.execute(select(PineScript).order_by(PineScript.updated_at.desc())).scalars().all()
    return {"items": [_serialize_pine_script(db, s) for s in rows]}


@pine_ai_router.post("/pine/analyze")
def analyze_pine_endpoint(payload: PineAnalyzeRequest) -> dict[str, Any]:
    try:
        return analyze_pine_script(payload.source_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@pine_ai_router.post("/pine/scripts", status_code=status.HTTP_201_CREATED)
def save_pine_script(
    payload: PineSaveRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    ensure_default_pine_scripts(db)
    try:
        analysis = analyze_pine_script(payload.source_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _, current_user = ctx
    if payload.script_id:
        script = db.execute(select(PineScript).where(PineScript.id == payload.script_id)).scalar_one_or_none()
        if script is None:
            raise HTTPException(status_code=404, detail="Pine script not found")
        latest = db.execute(
            select(PineScriptVersion)
            .where(PineScriptVersion.script_id == script.id)
            .order_by(PineScriptVersion.version_no.desc())
            .limit(1)
        ).scalar_one_or_none()
        next_no = (latest.version_no + 1) if latest else 1
    else:
        script = PineScript(
            owner_id=current_user.id if current_user else None,
            name=(payload.name or analysis["title"]).strip(),
            script_type=analysis["script_type"],
        )
        db.add(script)
        db.flush()
        next_no = 1

    ver = PineScriptVersion(
        script_id=script.id,
        version_no=next_no,
        source_code=payload.source_code,
        pine_version=analysis["pine_version"],
        ast_json=analysis["ast"],
        compat_report_json={
            **analysis["compat_report"],
            "inputs": analysis["inputs"],
            "builtin_indicators": analysis["builtin_indicators"],
        },
        sha256=analysis["sha256"],
    )
    db.add(ver)
    db.flush()
    script.current_version_id = ver.id
    script.updated_at = utcnow()
    db.commit()
    return _serialize_pine_script(db, script)


@pine_ai_router.post("/pine/execute")
def execute_pine_endpoint(
    payload: PineExecuteRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    if payload.timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")

    try:
        synced = sync_and_get_candles(
            db, client, symbol=payload.symbol, timeframe=payload.timeframe, limit=payload.limit
        )
    except MexcApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        res = execute_pine_script(payload.source_code, synced["items"], payload.input_overrides)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "symbol": synced["symbol"],
        "timeframe": synced["timeframe"],
        "candles": synced["items"],
        **res,
    }


def _has_gemini_credential(db: Session) -> bool:
    cnt = db.execute(
        select(func.count(ApiCredential.id)).where(
            ApiCredential.provider_type == "ai",
            ApiCredential.provider_name == "gemini",
        )
    ).scalar_one()
    return int(cnt) > 0


@pine_ai_router.post("/ai/strategy-builder", status_code=status.HTTP_201_CREATED)
def ai_strategy_builder(
    payload: AiStrategyBuilderRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    ensure_default_strategies(db)
    gemini_ready = _has_gemini_credential(db)
    generated = _ai_manager.generate_strategy_draft(
        payload.prompt,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        gemini_configured=gemini_ready,
    )

    _, current_user = ctx
    defn = generated["definition"]
    strat = Strategy(
        owner_id=current_user.id if current_user else None,
        name=generated["name"],
        description=generated["description"],
        status="Draft",
    )
    db.add(strat)
    db.flush()

    ver = StrategyVersion(
        strategy_id=strat.id,
        version_no=1,
        definition_json=defn,
        definition_hash=compute_definition_hash(defn),
        change_note="AI generated Draft strategy",
    )
    db.add(ver)
    db.flush()
    strat.current_version_id = ver.id

    conv = AiConversation(
        owner_id=current_user.id if current_user else None,
        provider=generated["provider_used"],
        topic=f"Strategy Builder: {generated['name']}",
        messages_json=[
            {"role": "user", "content": payload.prompt},
            {"role": "assistant", "content": generated["explanation"]},
        ],
    )
    db.add(conv)
    db.flush()

    sug = AiSuggestion(
        conversation_id=conv.id,
        kind="strategy_draft",
        prompt=payload.prompt,
        proposal_json={"strategy_id": strat.id, "strategy_version_id": ver.id, "definition": defn},
        explanation=generated["explanation"],
        status="pending",
    )
    db.add(sug)

    if current_user is not None:
        append_audit_log(
            db,
            actor=current_user.email,
            action="ai.strategy_draft_generated",
            entity=f"strategy:{strat.id}",
            payload={"provider": generated["provider_used"], "status": "Draft"},
            owner_id=current_user.id,
        )

    db.commit()
    return {
        "strategy_id": strat.id,
        "strategy_version_id": ver.id,
        "suggestion_id": sug.id,
        **generated,
    }


@pine_ai_router.post("/ai/research")
def ai_research_endpoint(
    payload: AiResearchRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    gemini_ready = _has_gemini_credential(db)
    metrics: dict[str, Any] = {}
    strategy_name = "Portfolio Strategy"
    symbol = "BTC/USDT"

    if payload.backtest_job_id:
        job = db.execute(select(BacktestJob).where(BacktestJob.id == payload.backtest_job_id)).scalar_one_or_none()
        if job is not None:
            metrics = job.metrics_json or {}
            symbol = job.symbol
            ver = db.execute(select(StrategyVersion).where(StrategyVersion.id == job.strategy_version_id)).scalar_one_or_none()
            if ver:
                st = db.execute(select(Strategy).where(Strategy.id == ver.strategy_id)).scalar_one_or_none()
                if st:
                    strategy_name = st.name
    elif payload.strategy_id:
        st = db.execute(select(Strategy).where(Strategy.id == payload.strategy_id)).scalar_one_or_none()
        if st:
            strategy_name = st.name

    analysis = _ai_manager.analyze_strategy_research(
        strategy_name=strategy_name,
        metrics=metrics,
        symbol=symbol,
        gemini_configured=gemini_ready,
    )

    _, current_user = ctx
    conv = AiConversation(
        owner_id=current_user.id if current_user else None,
        provider=analysis["provider_used"],
        topic=f"Research: {strategy_name}",
        messages_json=[
            {"role": "user", "content": payload.prompt},
            {"role": "assistant", "content": analysis["summary"]},
        ],
    )
    db.add(conv)
    db.flush()

    sug = AiSuggestion(
        conversation_id=conv.id,
        kind="optimization",
        prompt=payload.prompt,
        proposal_json=analysis["proposal"],
        explanation=analysis["summary"],
        status="pending",
    )
    db.add(sug)
    db.commit()

    return {
        "suggestion_id": sug.id,
        "strategy_name": strategy_name,
        "symbol": symbol,
        **analysis,
    }


@pine_ai_router.get("/ai/market-intelligence")
def ai_market_intelligence(
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    try:
        tickers = client.get_24h_tickers(DEFAULT_SPOT_SYMBOLS)
    except MexcApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _ai_manager.build_market_intelligence(tickers)


@pine_ai_router.get("/ai/suggestions")
def list_ai_suggestions(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute(select(AiSuggestion).order_by(AiSuggestion.created_at.desc()).limit(50)).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "kind": r.kind,
                "prompt": r.prompt,
                "proposal": r.proposal_json,
                "explanation": r.explanation,
                "status": r.status,
                "created_at": _iso(r.created_at),
                "decided_at": _iso(r.decided_at) if r.decided_at else None,
            }
            for r in rows
        ]
    }


@pine_ai_router.post("/ai/suggestions/{suggestion_id}/decision")
def decide_ai_suggestion(
    suggestion_id: str,
    payload: AiDecisionRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    sug = db.execute(select(AiSuggestion).where(AiSuggestion.id == suggestion_id)).scalar_one_or_none()
    if sug is None:
        raise HTTPException(status_code=404, detail="AI suggestion not found")

    sug.status = payload.decision
    sug.decided_at = utcnow()
    _, current_user = ctx
    if current_user is not None:
        append_audit_log(
            db,
            actor=current_user.email,
            action=f"ai.suggestion_{payload.decision}",
            entity=f"ai_suggestion:{sug.id}",
            payload={"kind": sug.kind, "status": sug.status},
            owner_id=current_user.id,
        )
    db.commit()
    return {"id": sug.id, "status": sug.status, "decided_at": _iso(sug.decided_at)}
