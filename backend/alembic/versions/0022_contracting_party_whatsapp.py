"""contracting party whatsapp

Revision ID: 0022_contracting_party_whatsapp
Revises: 0021_password_change_required
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_contracting_party_whatsapp"
down_revision: str | None = "0021_password_change_required"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contracting_parties",
        sa.Column("contact_whatsapp", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contracting_parties", "contact_whatsapp")
