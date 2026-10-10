"""contracting parties: who hires the company, separate from the served site

Revision ID: 0018_contracting_parties
Revises: 0017_development_details
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_contracting_parties"
down_revision: str | None = "0017_development_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contracting_parties",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("person_type", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("trade_name", sa.String(length=200), nullable=True),
        sa.Column("document", sa.String(length=32), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("contact_phone", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "document", name="uq_contracting_parties_tenant_document"
        ),
    )
    op.create_index("ix_contracting_parties_tenant_id", "contracting_parties", ["tenant_id"])
    op.create_index("ix_contracting_parties_name", "contracting_parties", ["name"])

    op.add_column("developments", sa.Column("contracting_party_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_developments_contracting_party",
        "developments",
        "contracting_parties",
        ["contracting_party_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_developments_contracting_party_id", "developments", ["contracting_party_id"]
    )

    # Cada empreendimento ja cadastrado ganha um contratante com o mesmo nome e CNPJ,
    # para ninguem ficar sem contratante. Depois eles podem ser reunidos pelo cadastro.
    op.execute(
        """
        WITH created AS (
            INSERT INTO contracting_parties (
                id, tenant_id, person_type, name, document,
                contact_email, contact_phone, is_active, created_at, updated_at
            )
            SELECT
                d.id, d.tenant_id, 'PJ', d.name, d.document,
                d.contact_email, d.contact_phone, true, now(), now()
            FROM developments d
            RETURNING id
        )
        UPDATE developments d
        SET contracting_party_id = created.id
        FROM created
        WHERE created.id = d.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_developments_contracting_party_id", table_name="developments")
    op.drop_constraint("fk_developments_contracting_party", "developments", type_="foreignkey")
    op.drop_column("developments", "contracting_party_id")
    op.drop_table("contracting_parties")
