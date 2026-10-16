"""development details: type, split address, geolocation, units, access hours, facade photo

Revision ID: 0017_development_details
Revises: 0016_collaborators
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_development_details"
down_revision: str | None = "0016_collaborators"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# address_line continua sendo o logradouro: os enderecos ja cadastrados ficam nele, sem conversao.
def _new_columns() -> list[sa.Column]:
    return [
        sa.Column("development_type", sa.String(length=60), nullable=True),
        sa.Column("address_number", sa.String(length=20), nullable=True),
        sa.Column("address_complement", sa.String(length=120), nullable=True),
        sa.Column("address_district", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("units_count", sa.Integer(), nullable=True),
        sa.Column("access_hours", sa.String(length=255), nullable=True),
        sa.Column("facade_photo_key", sa.String(length=512), nullable=True),
        sa.Column("facade_photo_content_type", sa.String(length=100), nullable=True),
    ]


def upgrade() -> None:
    for column in _new_columns():
        op.add_column("developments", column)


def downgrade() -> None:
    for column in reversed(_new_columns()):
        op.drop_column("developments", column.name)
