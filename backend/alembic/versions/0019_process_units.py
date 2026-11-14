"""process units between station and asset

Revision ID: 0019_process_units
Revises: 0018_contracting_parties
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_process_units"
down_revision: str | None = "0018_contracting_parties"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "process_unit_types",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=True),
        sa.Column("stage", sa.String(length=60), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_process_unit_types_tenant_name"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_process_unit_types_tenant_code"),
    )
    op.create_index("ix_process_unit_types_tenant_id", "process_unit_types", ["tenant_id"])

    op.create_table(
        "process_units",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("unit_type_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["unit_type_id"], ["process_unit_types.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "tenant_id", "station_id", "name", name="uq_process_units_station_name"
        ),
    )
    op.create_index("ix_process_units_tenant_id", "process_units", ["tenant_id"])
    op.create_index("ix_process_units_station_id", "process_units", ["station_id"])
    op.create_index("ix_process_units_unit_type_id", "process_units", ["unit_type_id"])

    # Equipamentos ja cadastrados ficam sem unidade (area geral) ate serem organizados.
    op.add_column("assets", sa.Column("process_unit_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_assets_process_unit",
        "assets",
        "process_units",
        ["process_unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_assets_process_unit_id", "assets", ["process_unit_id"])


def downgrade() -> None:
    op.drop_index("ix_assets_process_unit_id", table_name="assets")
    op.drop_constraint("fk_assets_process_unit", "assets", type_="foreignkey")
    op.drop_column("assets", "process_unit_id")
    op.drop_table("process_units")
    op.drop_table("process_unit_types")
