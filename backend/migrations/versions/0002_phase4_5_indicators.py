"""Phase 4 and 5 indicator catalog, parameters, and saved presets.

Revision ID: 0002_phase4_5_indicators
Revises: 0001_phase2_foundation
Create Date: 2026-11-18
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_phase4_5_indicators"
down_revision: Union[str, Sequence[str], None] = "0001_phase2_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "indicators",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("pane", sa.String(length=24), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("outputs_json", sa.JSON(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "indicator_parameters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("indicator_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("param_type", sa.String(length=24), nullable=False),
        sa.Column("default_value", sa.JSON(), nullable=False),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["indicator_id"], ["indicators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_indicator_parameters_indicator_id", "indicator_parameters", ["indicator_id"])

    op.create_table(
        "indicator_presets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("indicator_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["indicator_id"], ["indicators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_indicator_presets_owner_id", "indicator_presets", ["owner_id"])
    op.create_index("ix_indicator_presets_indicator_id", "indicator_presets", ["indicator_id"])


def downgrade() -> None:
    op.drop_index("ix_indicator_presets_indicator_id", table_name="indicator_presets")
    op.drop_index("ix_indicator_presets_owner_id", table_name="indicator_presets")
    op.drop_table("indicator_presets")
    op.drop_index("ix_indicator_parameters_indicator_id", table_name="indicator_parameters")
    op.drop_table("indicator_parameters")
    op.drop_table("indicators")
