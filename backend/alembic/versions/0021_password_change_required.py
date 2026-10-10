"""users must change a provisional password before using the app

Revision ID: 0021_password_change_required
Revises: 0020_visit_asset_situations
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021_password_change_required"
down_revision: str | None = "0020_visit_asset_situations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Quem ja tem acesso continua entrando normalmente: a marca nasce desligada.
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
