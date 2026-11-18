"""Phases 6 to 16 complete schema: strategies, backtesting, replay, pine, AI, risk & trading updates.

Revision ID: 0003_phases6_to_16_complete
Revises: 0002_phase4_5_indicators
Create Date: 2026-11-18
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_phases6_to_16_complete"
down_revision: Union[str, Sequence[str], None] = "0002_phase4_5_indicators"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("risk_profiles") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.add_column(
            sa.Column("emergency_stop_active", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("paper_accounts") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=True)

    with op.batch_alter_table("live_authorizations") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=True)

    with op.batch_alter_table("live_orders") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=True)

    op.create_table(
        "strategies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategies_owner_id", "strategies", ["owner_id"])

    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("definition_hash", sa.String(length=64), nullable=False),
        sa.Column("change_note", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "version_no", name="uq_strategy_version_no"),
    )
    op.create_index("ix_strategy_versions_strategy_id", "strategy_versions", ["strategy_id"])

    op.create_table(
        "backtest_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("strategy_version_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("data_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("trades_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["strategy_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_jobs_strategy_version_id", "backtest_jobs", ["strategy_version_id"])

    op.create_table(
        "replay_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("candles_json", sa.JSON(), nullable=False),
        sa.Column("cursor_index", sa.Integer(), nullable=False),
        sa.Column("total_bars", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pine_scripts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("script_type", sa.String(length=32), nullable=False),
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pine_scripts_owner_id", "pine_scripts", ["owner_id"])

    op.create_table(
        "pine_script_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("script_id", sa.String(length=36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("pine_version", sa.Integer(), nullable=False),
        sa.Column("ast_json", sa.JSON(), nullable=False),
        sa.Column("compat_report_json", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["script_id"], ["pine_scripts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("script_id", "version_no", name="uq_pine_script_version_no"),
    )
    op.create_index("ix_pine_script_versions_script_id", "pine_script_versions", ["script_id"])

    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("topic", sa.String(length=140), nullable=False),
        sa.Column("messages_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_conversations_owner_id", "ai_conversations", ["owner_id"])

    op.create_table(
        "ai_suggestions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("proposal_json", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_suggestions_conversation_id", "ai_suggestions", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_suggestions_conversation_id", table_name="ai_suggestions")
    op.drop_table("ai_suggestions")
    op.drop_index("ix_ai_conversations_owner_id", table_name="ai_conversations")
    op.drop_table("ai_conversations")
    op.drop_index("ix_pine_script_versions_script_id", table_name="pine_script_versions")
    op.drop_table("pine_script_versions")
    op.drop_index("ix_pine_scripts_owner_id", table_name="pine_scripts")
    op.drop_table("pine_scripts")
    op.drop_table("replay_sessions")
    op.drop_index("ix_backtest_jobs_strategy_version_id", table_name="backtest_jobs")
    op.drop_table("backtest_jobs")
    op.drop_index("ix_strategy_versions_strategy_id", table_name="strategy_versions")
    op.drop_table("strategy_versions")
    op.drop_index("ix_strategies_owner_id", table_name="strategies")
    op.drop_table("strategies")

    with op.batch_alter_table("live_orders") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=False)
    with op.batch_alter_table("live_authorizations") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=False)
    with op.batch_alter_table("paper_accounts") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=False)
    with op.batch_alter_table("risk_profiles") as batch_op:
        batch_op.drop_column("emergency_stop_active")
        batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=False)
