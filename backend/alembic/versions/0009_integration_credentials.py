"""iAnalisys integration credentials

Revision ID: 0009_integration_credentials
Revises: 0008_visit_planning
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_integration_credentials"
down_revision: str | None = "0008_visit_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_integration_credential_name"
        ),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(
        "ix_integration_credentials_tenant_id",
        "integration_credentials",
        ["tenant_id"],
    )
    op.create_index(
        "ix_integration_credentials_key_prefix",
        "integration_credentials",
        ["key_prefix"],
    )
    op.create_index(
        "ix_integration_credentials_key_hash",
        "integration_credentials",
        ["key_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("integration_credentials")
