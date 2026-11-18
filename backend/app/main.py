from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.backtest_replay import bt_replay_router
from app.api.copilot import copilot_router
from app.api.indicators import indicators_router
from app.api.market import market_router
from app.api.pine_ai import pine_ai_router
from app.api.router import router as v1_router
from app.api.strategies import strategies_router
from app.api.trading_risk import trading_risk_router
from app.api.updates import updates_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="APEX AI Trading Lab API",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)
    app.include_router(market_router)
    app.include_router(indicators_router)
    app.include_router(strategies_router)
    app.include_router(bt_replay_router)
    app.include_router(pine_ai_router)
    app.include_router(copilot_router)
    app.include_router(trading_risk_router)
    app.include_router(updates_router)
    return app


app = create_app()
