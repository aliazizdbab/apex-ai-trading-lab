"""Add ai_copilot_configs table for multi-provider agentic AI chatbot settings.

Revision ID: 0004_ai_copilot_config
Revises: 0003_phases6_to_16_complete
Create Date: 2026-11-18
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_ai_copilot_config"
down_revision: Union[str, Sequence[str], None] = "0003_phases6_to_16_complete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_copilot_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("api_key_masked", sa.String(length=64), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("autonomy_level", sa.String(length=32), nullable=False),
        sa.Column("system_instructions", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_copilot_configs_owner_id", "ai_copilot_configs", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_copilot_configs_owner_id", table_name="ai_copilot_configs")
    op.drop_table("ai_copilot_configs")
