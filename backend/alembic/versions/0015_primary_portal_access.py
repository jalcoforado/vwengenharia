"""development contact data, primary responsibility and explicit portal access

Revision ID: 0015_primary_portal_access
Revises: 0014_client_development_contacts
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_primary_portal_access"
down_revision: str | None = "0014_client_development_contacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("developments", sa.Column("document", sa.String(length=32), nullable=True))
    op.add_column("developments", sa.Column("contact_phone", sa.String(length=40), nullable=True))
    op.add_column("developments", sa.Column("contact_email", sa.String(length=320), nullable=True))
    op.create_unique_constraint(
        "uq_developments_tenant_document", "developments", ["tenant_id", "document"]
    )

    op.add_column(
        "client_development_contacts",
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "client_development_contacts",
        sa.Column("portal_access", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # O responsavel principal (developments.client_id) passa a existir tambem como
    # responsabilidade. Quem ja tinha login de portal ligado a esse responsavel
    # enxergava o empreendimento; a liberacao e preservada para ninguem perder acesso.
    op.execute(
        """
        INSERT INTO client_development_contacts (
            id, tenant_id, client_id, development_id, scope,
            is_primary, portal_access, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), d.tenant_id, d.client_id, d.id, 'GERAL',
            true,
            EXISTS (
                SELECT 1 FROM client_membership_access a
                WHERE a.tenant_id = d.tenant_id AND a.client_id = d.client_id
            ),
            true, now(), now()
        FROM developments d
        """
    )

    op.create_index(
        "uq_client_development_contacts_primary",
        "client_development_contacts",
        ["tenant_id", "development_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_client_development_contacts_primary",
        table_name="client_development_contacts",
    )
    op.execute("DELETE FROM client_development_contacts WHERE is_primary")
    op.drop_column("client_development_contacts", "portal_access")
    op.drop_column("client_development_contacts", "is_primary")
    op.drop_constraint("uq_developments_tenant_document", "developments", type_="unique")
    op.drop_column("developments", "contact_email")
    op.drop_column("developments", "contact_phone")
    op.drop_column("developments", "document")
