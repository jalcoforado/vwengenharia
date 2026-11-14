"""station code sequences

Revision ID: 0023_station_code_sequences
Revises: 0022_contracting_party_whatsapp
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_station_code_sequences"
down_revision: str | None = "0022_contracting_party_whatsapp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ultimo numero emitido por prefixo de codigo (ex.: "ETE-RLA-"), para nunca
    # reaproveitar um codigo que ja foi de outra estacao. Sem carga: o primeiro uso de
    # cada prefixo parte do maior numero que ja existe nas estacoes.
    op.create_table(
        "station_code_sequences",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("prefix", sa.String(length=40), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id", "prefix", name="pk_station_code_sequences"),
    )


def downgrade() -> None:
    op.drop_table("station_code_sequences")
