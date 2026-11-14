"""client portal access mapping

Revision ID: 0013_client_portal_access
Revises: 0012_legacy_migration
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_client_portal_access"
down_revision: str | None = "0012_legacy_migration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_membership_access",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "membership_id",
            "client_id",
            name="uq_client_membership_access",
        ),
    )
    op.create_index(
        "ix_client_membership_access_tenant_id",
        "client_membership_access",
        ["tenant_id"],
    )
    op.create_index(
        "ix_client_membership_access_membership_id",
        "client_membership_access",
        ["membership_id"],
    )
    op.create_index(
        "ix_client_membership_access_client_id",
        "client_membership_access",
        ["client_id"],
    )


def downgrade() -> None:
    op.drop_table("client_membership_access")
