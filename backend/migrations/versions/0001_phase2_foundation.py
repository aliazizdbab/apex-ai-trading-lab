"""Phase 2 foundation schema.

Revision ID: 0001_phase2_foundation
Revises:
Create Date: 2026-11-18
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_phase2_foundation"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False),
        sa.Column("preferences_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "exchange_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exchange_connections_owner_id", "exchange_connections", ["owner_id"])

    op.create_table(
        "api_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("connection_id", sa.String(length=36), nullable=True),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("api_key_masked", sa.String(length=64), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("api_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["connection_id"], ["exchange_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_credentials_owner_id", "api_credentials", ["owner_id"])

    op.create_table(
        "symbols",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("base", sa.String(length=16), nullable=False),
        sa.Column("quote", sa.String(length=16), nullable=False),
        sa.Column("price_precision", sa.Integer(), nullable=False),
        sa.Column("qty_precision", sa.Integer(), nullable=False),
        sa.Column("min_qty", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("min_notional", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange", "symbol", name="uq_exchange_symbol"),
    )

    op.create_table(
        "candles",
        sa.Column("symbol_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("o", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("h", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("l", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("c", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("volume", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("symbol_id", "timeframe", "open_time"),
    )
    op.create_index("ix_candles_symbol_tf_time", "candles", ["symbol_id", "timeframe", "open_time"])

    op.create_table(
        "candle_coverage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("from_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gap_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candle_coverage_symbol_id", "candle_coverage", ["symbol_id"])

    op.create_table(
        "risk_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("max_risk_per_trade_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("max_daily_loss_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("max_weekly_loss_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("max_drawdown_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("max_open_positions", sa.Integer(), nullable=False),
        sa.Column("max_asset_exposure_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_profiles_owner_id", "risk_profiles", ["owner_id"])

    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("initial_balance_usdt", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("available_usdt", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_accounts_owner_id", "paper_accounts", ["owner_id"])

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_account_id", sa.String(length=36), nullable=False),
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("symbol_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("order_type", sa.String(length=24), nullable=False),
        sa.Column("qty", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("price", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["paper_account_id"], ["paper_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id"),
    )
    op.create_index("ix_paper_orders_paper_account_id", "paper_orders", ["paper_account_id"])

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_order_id", sa.String(length=36), nullable=False),
        sa.Column("price", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("qty", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("fee", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("fee_asset", sa.String(length=16), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["paper_order_id"], ["paper_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_trades_paper_order_id", "paper_trades", ["paper_order_id"])

    op.create_table(
        "live_authorizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("strategy_version_id", sa.String(length=64), nullable=False),
        sa.Column("capital_mode", sa.String(length=24), nullable=False),
        sa.Column("capital_value", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("risk_profile_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["risk_profile_id"], ["risk_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_authorizations_owner_id", "live_authorizations", ["owner_id"])

    op.create_table(
        "live_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("authorization_id", sa.String(length=36), nullable=False),
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("exchange_order_id", sa.String(length=128), nullable=True),
        sa.Column("symbol_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("order_type", sa.String(length=24), nullable=False),
        sa.Column("qty", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("price", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_approval_token", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["authorization_id"], ["live_authorizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id"),
    )
    op.create_index("ix_live_orders_owner_id", "live_orders", ["owner_id"])

    op.create_table(
        "live_trades",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("live_order_id", sa.String(length=36), nullable=False),
        sa.Column("exchange_trade_id", sa.String(length=128), nullable=False),
        sa.Column("price", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("qty", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("fee", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("fee_asset", sa.String(length=16), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["live_order_id"], ["live_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_trade_id"),
    )
    op.create_index("ix_live_trades_live_order_id", "live_trades", ["live_order_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("level", sa.String(length=24), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_owner_id", "notifications", ["owner_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity", sa.String(length=120), nullable=False),
        sa.Column("payload_redacted", sa.JSON(), nullable=False),
        sa.Column("hash_prev", sa.String(length=64), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_hash"),
    )
    op.create_index("ix_audit_logs_owner_id", "audit_logs", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_owner_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_notifications_owner_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_live_trades_live_order_id", table_name="live_trades")
    op.drop_table("live_trades")
    op.drop_index("ix_live_orders_owner_id", table_name="live_orders")
    op.drop_table("live_orders")
    op.drop_index("ix_live_authorizations_owner_id", table_name="live_authorizations")
    op.drop_table("live_authorizations")
    op.drop_index("ix_paper_trades_paper_order_id", table_name="paper_trades")
    op.drop_table("paper_trades")
    op.drop_index("ix_paper_orders_paper_account_id", table_name="paper_orders")
    op.drop_table("paper_orders")
    op.drop_index("ix_paper_accounts_owner_id", table_name="paper_accounts")
    op.drop_table("paper_accounts")
    op.drop_index("ix_risk_profiles_owner_id", table_name="risk_profiles")
    op.drop_table("risk_profiles")
    op.drop_index("ix_candle_coverage_symbol_id", table_name="candle_coverage")
    op.drop_table("candle_coverage")
    op.drop_index("ix_candles_symbol_tf_time", table_name="candles")
    op.drop_table("candles")
    op.drop_table("symbols")
    op.drop_index("ix_api_credentials_owner_id", table_name="api_credentials")
    op.drop_table("api_credentials")
    op.drop_index("ix_exchange_connections_owner_id", table_name="exchange_connections")
    op.drop_table("exchange_connections")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
