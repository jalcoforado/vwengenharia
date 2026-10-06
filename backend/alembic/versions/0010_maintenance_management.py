"""maintenance management

Revision ID: 0010_maintenance_management
Revises: 0009_integration_credentials
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_maintenance_management"
down_revision: str | None = "0009_integration_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance_plans",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_membership_id", sa.Uuid(), nullable=True),
        sa.Column("maintenance_type", sa.String(length=24), nullable=False),
        sa.Column("frequency_days", sa.Integer(), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assigned_membership_id"], ["memberships.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_maintenance_plans_tenant_id", "maintenance_plans", ["tenant_id"])
    op.create_index("ix_maintenance_plans_asset_id", "maintenance_plans", ["asset_id"])
    op.create_index(
        "ix_maintenance_plans_assigned_membership_id",
        "maintenance_plans",
        ["assigned_membership_id"],
    )
    op.create_index("ix_maintenance_plans_next_due_at", "maintenance_plans", ["next_due_at"])

    op.create_table(
        "maintenance_executions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("maintenance_plan_id", sa.Uuid(), nullable=True),
        sa.Column("work_order_id", sa.Uuid(), nullable=True),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("performed_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("maintenance_type", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["maintenance_plan_id"], ["maintenance_plans.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["performed_by_membership_id"], ["memberships.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_maintenance_executions_tenant_id",
        "maintenance_executions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_maintenance_executions_maintenance_plan_id",
        "maintenance_executions",
        ["maintenance_plan_id"],
    )
    op.create_index(
        "ix_maintenance_executions_work_order_id",
        "maintenance_executions",
        ["work_order_id"],
    )
    op.create_index(
        "ix_maintenance_executions_asset_id",
        "maintenance_executions",
        ["asset_id"],
    )
    op.create_index(
        "ix_maintenance_executions_performed_by_membership_id",
        "maintenance_executions",
        ["performed_by_membership_id"],
    )
    op.create_index(
        "ix_maintenance_executions_completed_at",
        "maintenance_executions",
        ["completed_at"],
    )


def downgrade() -> None:
    op.drop_table("maintenance_executions")
    op.drop_table("maintenance_plans")
