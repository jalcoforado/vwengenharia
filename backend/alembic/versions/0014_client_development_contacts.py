"""client contact fields and development responsibility mapping

Revision ID: 0014_client_development_contacts
Revises: 0013_client_portal_access
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_client_development_contacts"
down_revision: str | None = "0013_client_portal_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("contact_role", sa.String(length=120), nullable=True))
    op.add_column("clients", sa.Column("contact_whatsapp", sa.String(length=40), nullable=True))

    op.create_table(
        "client_development_contacts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("development_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["development_id"], ["developments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "client_id",
            "development_id",
            "scope",
            name="uq_client_development_contacts",
        ),
    )
    op.create_index(
        "ix_client_development_contacts_tenant_id",
        "client_development_contacts",
        ["tenant_id"],
    )
    op.create_index(
        "ix_client_development_contacts_client_id",
        "client_development_contacts",
        ["client_id"],
    )
    op.create_index(
        "ix_client_development_contacts_development_id",
        "client_development_contacts",
        ["development_id"],
    )


def downgrade() -> None:
    op.drop_table("client_development_contacts")
    op.drop_column("clients", "contact_whatsapp")
    op.drop_column("clients", "contact_role")
