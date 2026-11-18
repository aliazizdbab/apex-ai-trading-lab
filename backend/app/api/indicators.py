from __future__ import annotations

from dataclasses import asdict
from datetime import timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.router import get_optional_session_and_user
from app.db.models import (
    IndicatorCatalog,
    IndicatorParameter,
    SavedIndicatorPreset,
    User,
    UserSession,
    utcnow,
)
from app.db.session import get_db
from app.services.audit import append_audit_log
from app.services.market_data import TIMEFRAME_SECONDS, sync_and_get_candles
from app.services.mexc_provider import get_mexc_client
from engine.indicators.catalog import (
    INDICATOR_SPECS,
    get_indicator_spec,
    validate_and_coerce_params,
)
from engine.indicators.compute import compute_heikin_ashi, compute_indicator
from exchanges.mexc.market_client import MexcApiError, MexcMarketDataClient

indicators_router = APIRouter(prefix="/api/v1/indicators")


def _iso_utc(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def ensure_builtin_indicators(db: Session) -> None:
    """Seed or update the 11 built-in indicators and default presets when catalog is empty."""
    was_empty = db.execute(select(IndicatorCatalog.id).limit(1)).scalar_one_or_none() is None

    for spec in INDICATOR_SPECS.values():
        outputs_list = [asdict(o) for o in spec.outputs]
        row = db.execute(
            select(IndicatorCatalog).where(IndicatorCatalog.id == spec.id)
        ).scalar_one_or_none()
        if row is None:
            row = IndicatorCatalog(
                id=spec.id,
                name=spec.name,
                category=spec.category,
                kind="builtin",
                pane=spec.pane,
                description=spec.description,
                outputs_json=outputs_list,
                current_version=1,
            )
            db.add(row)
            db.flush()
        else:
            row.name = spec.name
            row.category = spec.category
            row.pane = spec.pane
            row.description = spec.description
            row.outputs_json = outputs_list
            row.updated_at = utcnow()

        existing_params = {
            p.name: p
            for p in db.execute(
                select(IndicatorParameter).where(IndicatorParameter.indicator_id == spec.id)
            )
            .scalars()
            .all()
        }
        for p in spec.parameters:
            existing_p = existing_params.get(p.name)
            opts = list(p.options) if p.options else None
            if existing_p is None:
                db.add(
                    IndicatorParameter(
                        indicator_id=spec.id,
                        name=p.name,
                        label=p.label,
                        param_type=p.param_type,
                        default_value=p.default,
                        min_value=p.min_val,
                        max_value=p.max_val,
                        options_json=opts,
                    )
                )
            else:
                existing_p.label = p.label
                existing_p.param_type = p.param_type
                existing_p.default_value = p.default
                existing_p.min_value = p.min_val
                existing_p.max_value = p.max_val
                existing_p.options_json = opts

    if was_empty:
        preset_count = db.execute(select(func.count(SavedIndicatorPreset.id))).scalar_one()
        if preset_count == 0:
            db.add_all(
                [
                    SavedIndicatorPreset(
                        indicator_id="ema",
                        name="EMA 20",
                        symbol="BTC/USDT",
                        timeframe="15m",
                        params_json={"length": 20, "source": "close", "offset": 0},
                        visible=True,
                    ),
                    SavedIndicatorPreset(
                        indicator_id="bb",
                        name="Bollinger Bands (20, 2)",
                        symbol="BTC/USDT",
                        timeframe="15m",
                        params_json={"length": 20, "mult": 2.0, "source": "close"},
                        visible=True,
                    ),
                    SavedIndicatorPreset(
                        indicator_id="rsi",
                        name="RSI 14",
                        symbol="BTC/USDT",
                        timeframe="15m",
                        params_json={"length": 14, "source": "close", "overbought": 70, "oversold": 30},
                        visible=True,
                    ),
                ]
            )

    db.commit()


def _serialize_preset(row: SavedIndicatorPreset) -> dict[str, Any]:
    return {
        "id": row.id,
        "indicator_id": row.indicator_id,
        "name": row.name,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "params": row.params_json,
        "visible": row.visible,
        "created_at": _iso_utc(row.created_at),
        "updated_at": _iso_utc(row.updated_at),
    }


class PresetCreateRequest(BaseModel):
    indicator_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="15m", min_length=2, max_length=16)
    params: dict[str, Any] = Field(default_factory=dict)
    visible: bool = True


class PresetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    symbol: str | None = Field(default=None, min_length=3, max_length=32)
    timeframe: str | None = Field(default=None, min_length=2, max_length=16)
    params: dict[str, Any] | None = None
    visible: bool | None = None


class IndicatorComputeItem(BaseModel):
    instance_id: str = Field(min_length=1, max_length=64)
    indicator_id: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


class IndicatorComputeRequest(BaseModel):
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=32)
    timeframe: str = Field(default="15m", min_length=2, max_length=16)
    limit: int = Field(default=250, ge=20, le=1500)
    candle_mode: Literal["standard", "heikin_ashi"] = "standard"
    indicators: list[IndicatorComputeItem] = Field(default_factory=list)


@indicators_router.get("/catalog")
def get_indicator_catalog(db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_builtin_indicators(db)
    rows = db.execute(select(IndicatorCatalog).order_by(IndicatorCatalog.id.asc())).scalars().all()
    params_rows = db.execute(select(IndicatorParameter).order_by(IndicatorParameter.id.asc())).scalars().all()
    params_by_ind: dict[str, list[dict[str, Any]]] = {}
    for p in params_rows:
        params_by_ind.setdefault(p.indicator_id, []).append(
            {
                "name": p.name,
                "label": p.label,
                "param_type": p.param_type,
                "default": p.default_value,
                "min_val": p.min_value,
                "max_val": p.max_value,
                "options": p.options_json,
            }
        )

    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "category": r.category,
                "kind": r.kind,
                "pane": r.pane,
                "description": r.description,
                "outputs": r.outputs_json,
                "parameters": params_by_ind.get(r.id, []),
            }
            for r in rows
        ]
    }


@indicators_router.get("/presets")
def list_indicator_presets(db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_builtin_indicators(db)
    rows = db.execute(
        select(SavedIndicatorPreset).order_by(SavedIndicatorPreset.created_at.asc())
    ).scalars().all()
    return {"items": [_serialize_preset(r) for r in rows]}


@indicators_router.post("/presets", status_code=status.HTTP_201_CREATED)
def create_indicator_preset(
    payload: PresetCreateRequest,
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    ensure_builtin_indicators(db)
    try:
        validated_params = validate_and_coerce_params(payload.indicator_id, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _, current_user = ctx
    preset = SavedIndicatorPreset(
        owner_id=current_user.id if current_user else None,
        indicator_id=payload.indicator_id,
        name=payload.name.strip(),
        symbol=payload.symbol.strip().upper(),
        timeframe=payload.timeframe,
        params_json=validated_params,
        visible=payload.visible,
    )
    db.add(preset)
    db.flush()

    if current_user is not None:
        append_audit_log(
            db,
            actor=current_user.email,
            action="indicator_preset.created",
            entity=f"indicator_preset:{preset.id}",
            payload={"indicator_id": preset.indicator_id, "name": preset.name, "params": validated_params},
            owner_id=current_user.id,
        )

    db.commit()
    return _serialize_preset(preset)


@indicators_router.put("/presets/{preset_id}")
def update_indicator_preset(
    preset_id: str,
    payload: PresetUpdateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_builtin_indicators(db)
    preset = db.execute(
        select(SavedIndicatorPreset).where(SavedIndicatorPreset.id == preset_id)
    ).scalar_one_or_none()
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Indicator preset not found")

    if payload.name is not None:
        preset.name = payload.name.strip()
    if payload.symbol is not None:
        preset.symbol = payload.symbol.strip().upper()
    if payload.timeframe is not None:
        if payload.timeframe not in TIMEFRAME_SECONDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported timeframe")
        preset.timeframe = payload.timeframe
    if payload.params is not None:
        try:
            preset.params_json = validate_and_coerce_params(preset.indicator_id, payload.params)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if payload.visible is not None:
        preset.visible = payload.visible

    preset.updated_at = utcnow()
    db.commit()
    return _serialize_preset(preset)


@indicators_router.delete("/presets/{preset_id}")
def delete_indicator_preset(preset_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    preset = db.execute(
        select(SavedIndicatorPreset).where(SavedIndicatorPreset.id == preset_id)
    ).scalar_one_or_none()
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Indicator preset not found")
    db.delete(preset)
    db.commit()
    return {"ok": True}


@indicators_router.post("/compute")
def compute_indicators_endpoint(
    payload: IndicatorComputeRequest,
    db: Session = Depends(get_db),
    client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    if payload.timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported timeframe '{payload.timeframe}'",
        )

    try:
        synced = sync_and_get_candles(
            db,
            client,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            limit=payload.limit,
        )
    except MexcApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    candles = synced["items"]
    if payload.candle_mode == "heikin_ashi":
        candles = compute_heikin_ashi(candles)

    outputs: list[dict[str, Any]] = []
    for item in payload.indicators:
        try:
            spec = get_indicator_spec(item.indicator_id)
            validated = validate_and_coerce_params(item.indicator_id, item.params)
            series = compute_indicator(item.indicator_id, candles, validated)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        outputs.append(
            {
                "instance_id": item.instance_id,
                "indicator_id": spec.id,
                "name": spec.name,
                "pane": spec.pane,
                "params": validated,
                "outputs_meta": [asdict(o) for o in spec.outputs],
                "series": series,
            }
        )

    return {
        "symbol": synced["symbol"],
        "timeframe": synced["timeframe"],
        "source": synced["source"],
        "candle_mode": payload.candle_mode,
        "quality": synced["quality"],
        "candles": candles,
        "outputs": outputs,
    }
