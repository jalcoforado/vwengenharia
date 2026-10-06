"""ai runs

Revision ID: 0006_ai_runs
Revises: 0005_storage_hardening
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_ai_runs"
down_revision: str | None = "0005_storage_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("tool_trace", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_ai_runs_tenant_id", "ai_runs", ["tenant_id"])
    op.create_index("ix_ai_runs_user_id", "ai_runs", ["user_id"])
    op.create_index("ix_ai_runs_status", "ai_runs", ["status"])


def downgrade() -> None:
    op.drop_table("ai_runs")
