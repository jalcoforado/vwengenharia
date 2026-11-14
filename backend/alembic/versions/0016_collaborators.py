"""collaborators with optional credential

Revision ID: 0016_collaborators
Revises: 0015_primary_portal_access
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_collaborators"
down_revision: str | None = "0015_primary_portal_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collaborators",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("document", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("contact_phone", sa.String(length=40), nullable=True),
        sa.Column("contact_whatsapp", sa.String(length=40), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("membership_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "document", name="uq_collaborators_tenant_document"),
        sa.UniqueConstraint("membership_id", name="uq_collaborators_membership"),
    )
    op.create_index("ix_collaborators_tenant_id", "collaborators", ["tenant_id"])
    op.create_index("ix_collaborators_name", "collaborators", ["name"])

    # Quem ja tem credencial interna vira colaborador, ligado a credencial que ja usa.
    # Logins de portal (perfil CLIENTE) pertencem aos responsaveis e ficam de fora.
    op.execute(
        """
        INSERT INTO collaborators (
            id, tenant_id, name, contact_email, category,
            membership_id, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), m.tenant_id, u.name, u.email,
            CASE WHEN m.role IN ('TECNICO', 'MANUTENCAO') THEN 'TECNICO' ELSE 'BACKOFFICE' END,
            m.id, m.is_active, now(), now()
        FROM memberships m
        JOIN users u ON u.id = m.user_id
        WHERE m.role <> 'CLIENTE'
        """
    )


def downgrade() -> None:
    op.drop_table("collaborators")
