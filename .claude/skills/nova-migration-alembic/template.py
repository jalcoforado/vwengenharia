"""<descrição curta do que a migration faz, em inglês, como as demais>

Revision ID: NNNN_descricao_curta
Revises: <revision da migration anterior>
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# No máximo 32 caracteres (alembic_version.version_num).
revision: str = "NNNN_descricao_curta"
down_revision: str | None = "<revision da migration anterior>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Exemplo: tabela de negócio, sempre com tenant_id.
    op.create_table(
        "exemplos",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_exemplos_tenant_name"),
    )
    op.create_index("ix_exemplos_tenant_id", "exemplos", ["tenant_id"])

    # Exemplo: coluna nova em tabela com dados, sem quebrar quem já existe.
    op.add_column(
        "clients",
        sa.Column("exemplo_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("clients", "exemplo_flag")
    op.drop_table("exemplos")
