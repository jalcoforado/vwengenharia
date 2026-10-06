"""storage hardening

Revision ID: 0005_storage_hardening
Revises: 0004_operations_sla
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_storage_hardening"
down_revision: str | None = "0004_operations_sla"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attachments",
        sa.Column(
            "storage_status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column(
        "attachments",
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("attachments", "storage_status", server_default=None)


def downgrade() -> None:
    op.drop_column("attachments", "uploaded_at")
    op.drop_column("attachments", "storage_status")
