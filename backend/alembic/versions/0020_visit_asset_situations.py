"""asset situation recorded per visit

Revision ID: 0020_visit_asset_situations
Revises: 0019_process_units
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_visit_asset_situations"
down_revision: str | None = "0019_process_units"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visit_asset_situations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("situation", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("client_operation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id", "visit_id", "asset_id", name="uq_visit_asset_situations_visit_asset"
        ),
    )
    op.create_index(
        "ix_visit_asset_situations_tenant_id", "visit_asset_situations", ["tenant_id"]
    )
    op.create_index(
        "ix_visit_asset_situations_visit_id", "visit_asset_situations", ["visit_id"]
    )
    op.create_index(
        "ix_visit_asset_situations_asset_id", "visit_asset_situations", ["asset_id"]
    )


def downgrade() -> None:
    op.drop_table("visit_asset_situations")
