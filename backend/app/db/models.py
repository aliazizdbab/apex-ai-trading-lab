from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferences_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExchangeConnection(Base):
    __tablename__ = "exchange_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="disconnected", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class ApiCredential(Base):
    __tablename__ = "api_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("exchange_connections.id", ondelete="SET NULL"), nullable=True
    )
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key_masked: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Symbol(Base):
    __tablename__ = "symbols"
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_exchange_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    base: Mapped[str] = mapped_column(String(16), nullable=False)
    quote: Mapped[str] = mapped_column(String(16), nullable=False)
    price_precision: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_precision: Mapped[int] = mapped_column(Integer, nullable=False)
    min_qty: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    min_notional: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="trading", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (Index("ix_candles_symbol_tf_time", "symbol_id", "timeframe", "open_time"),)

    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(16), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    o: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    h: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    l: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    c: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="mexc", nullable=False)


class CandleCoverage(Base):
    __tablename__ = "candle_coverage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    from_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    gap_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    max_risk_per_trade_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    max_daily_loss_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    max_weekly_loss_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    max_drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    max_open_positions: Mapped[int] = mapped_column(Integer, nullable=False)
    max_asset_exposure_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emergency_stop_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    initial_balance_usdt: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    available_usdt: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    paper_account_id: Mapped[str] = mapped_column(
        ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_order_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id", ondelete="RESTRICT"), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    order_type: Mapped[str] = mapped_column(String(24), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    paper_order_id: Mapped[str] = mapped_column(
        ForeignKey("paper_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    fee_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class LiveAuthorization(Base):
    __tablename__ = "live_authorizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    strategy_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    capital_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    capital_value: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    risk_profile_id: Mapped[str] = mapped_column(
        ForeignKey("risk_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LiveOrder(Base):
    __tablename__ = "live_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    authorization_id: Mapped[str] = mapped_column(
        ForeignKey("live_authorizations.id", ondelete="RESTRICT"), nullable=False
    )
    client_order_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    exchange_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id", ondelete="RESTRICT"), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    order_type: Mapped[str] = mapped_column(String(24), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_approval_token: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class LiveTrade(Base):
    __tablename__ = "live_trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    live_order_id: Mapped[str] = mapped_column(
        ForeignKey("live_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exchange_trade_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    fee_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(24), default="info", nullable=False)
    category: Mapped[str] = mapped_column(String(48), default="system", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_redacted: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    hash_prev: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class IndicatorCatalog(Base):
    __tablename__ = "indicators"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), default="builtin", nullable=False)
    pane: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    outputs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class IndicatorParameter(Base):
    __tablename__ = "indicator_parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator_id: Mapped[str] = mapped_column(
        ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    param_type: Mapped[str] = mapped_column(String(24), nullable=False)
    default_value: Mapped[dict | list | str | int | float] = mapped_column(JSON, nullable=False)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    options_json: Mapped[list | None] = mapped_column(JSON, nullable=True)


class SavedIndicatorPreset(Base):
    __tablename__ = "indicator_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    indicator_id: Mapped[str] = mapped_column(
        ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), default="BTC/USDT", nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), default="15m", nullable=False)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="Draft", nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (UniqueConstraint("strategy_id", "version_no", name="uq_strategy_version_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    strategy_id: Mapped[str] = mapped_column(
        ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    definition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    change_note: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BacktestJob(Base):
    __tablename__ = "backtest_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    strategy_version_id: Mapped[str] = mapped_column(
        ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    data_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    trades_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReplaySession(Base):
    __tablename__ = "replay_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    candles_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    cursor_index: Mapped[int] = mapped_column(Integer, nullable=False)
    total_bars: Mapped[int] = mapped_column(Integer, nullable=False)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PineScript(Base):
    __tablename__ = "pine_scripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    script_type: Mapped[str] = mapped_column(String(32), default="indicator", nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PineScriptVersion(Base):
    __tablename__ = "pine_script_versions"
    __table_args__ = (UniqueConstraint("script_id", "version_no", name="uq_pine_script_version_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(
        ForeignKey("pine_scripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    pine_version: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    ast_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    compat_report_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    topic: Mapped[str] = mapped_column(String(140), nullable=False)
    messages_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AiSuggestion(Base):
    __tablename__ = "ai_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiCopilotConfig(Base):
    __tablename__ = "ai_copilot_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="builtin", nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), default="apex-quant-copilot-v1", nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    autonomy_level: Mapped[str] = mapped_column(String(32), default="full_copilot", nullable=False)
    system_instructions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
