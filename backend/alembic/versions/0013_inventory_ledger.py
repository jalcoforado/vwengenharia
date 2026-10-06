"""inventory ledger

Revision ID: 0013_inventory_ledger
Revises: 0012_legacy_migration
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_inventory_ledger"
down_revision: str | None = "0012_legacy_migration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("current_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_inventory_item_code"),
    )
    op.create_index("ix_inventory_items_tenant_id", "inventory_items", ["tenant_id"])

    op.add_column(
        "material_requests",
        sa.Column("inventory_item_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_material_requests_inventory_item_id",
        "material_requests",
        "inventory_items",
        ["inventory_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_material_requests_inventory_item_id",
        "material_requests",
        ["inventory_item_id"],
    )

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("performed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(length=24), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("balance_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("station_id", sa.Uuid(), nullable=True),
        sa.Column("work_order_id", sa.Uuid(), nullable=True),
        sa.Column("material_request_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["work_order_id"], ["work_orders.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["material_request_id"], ["material_requests.id"], ondelete="SET NULL"
        ),
    )
    for column in [
        "tenant_id",
        "inventory_item_id",
        "performed_by_user_id",
        "movement_type",
        "station_id",
        "work_order_id",
        "material_request_id",
    ]:
        op.create_index(
            f"ix_inventory_movements_{column}",
            "inventory_movements",
            [column],
        )


def downgrade() -> None:
    op.drop_table("inventory_movements")
    op.drop_index(
        "ix_material_requests_inventory_item_id",
        table_name="material_requests",
    )
    op.drop_constraint(
        "fk_material_requests_inventory_item_id",
        "material_requests",
        type_="foreignkey",
    )
    op.drop_column("material_requests", "inventory_item_id")
    op.drop_table("inventory_items")
