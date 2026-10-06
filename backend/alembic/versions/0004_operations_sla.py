"""operations sla and review

Revision ID: 0004_operations_sla
Revises: 0003_field_operations
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_operations_sla"
down_revision: str | None = "0003_field_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "occurrences",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=True),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("occurrence_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_occurrences_tenant_id", "occurrences", ["tenant_id"])
    op.create_index("ix_occurrences_visit_id", "occurrences", ["visit_id"])
    op.create_index("ix_occurrences_station_id", "occurrences", ["station_id"])
    op.create_index("ix_occurrences_asset_id", "occurrences", ["asset_id"])
    op.create_index("ix_occurrences_occurrence_type", "occurrences", ["occurrence_type"])
    op.create_index("ix_occurrences_severity", "occurrences", ["severity"])
    op.create_index("ix_occurrences_status", "occurrences", ["status"])
    op.create_index(
        "ix_occurrences_created_by_user_id", "occurrences", ["created_by_user_id"]
    )

    op.create_table(
        "work_orders",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("occurrence_id", sa.Uuid(), nullable=True),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_membership_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assigned_membership_id"], ["memberships.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["occurrence_id"], ["occurrences.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_work_orders_tenant_id", "work_orders", ["tenant_id"])
    op.create_index("ix_work_orders_occurrence_id", "work_orders", ["occurrence_id"])
    op.create_index("ix_work_orders_station_id", "work_orders", ["station_id"])
    op.create_index("ix_work_orders_asset_id", "work_orders", ["asset_id"])
    op.create_index(
        "ix_work_orders_assigned_membership_id",
        "work_orders",
        ["assigned_membership_id"],
    )
    op.create_index("ix_work_orders_priority", "work_orders", ["priority"])
    op.create_index("ix_work_orders_status", "work_orders", ["status"])
    op.create_index("ix_work_orders_sla_due_at", "work_orders", ["sla_due_at"])

    op.create_table(
        "work_order_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("work_order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["work_order_id"], ["work_orders.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_work_order_status_history_tenant_id",
        "work_order_status_history",
        ["tenant_id"],
    )
    op.create_index(
        "ix_work_order_status_history_work_order_id",
        "work_order_status_history",
        ["work_order_id"],
    )
    op.create_index(
        "ix_work_order_status_history_changed_by_user_id",
        "work_order_status_history",
        ["changed_by_user_id"],
    )
    op.create_index(
        "ix_work_order_status_history_changed_at",
        "work_order_status_history",
        ["changed_at"],
    )

    op.create_table(
        "visit_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "visit_id", name="uq_visit_review"),
    )
    op.create_index("ix_visit_reviews_tenant_id", "visit_reviews", ["tenant_id"])
    op.create_index("ix_visit_reviews_visit_id", "visit_reviews", ["visit_id"])
    op.create_index(
        "ix_visit_reviews_reviewer_user_id",
        "visit_reviews",
        ["reviewer_user_id"],
    )


def downgrade() -> None:
    op.drop_table("visit_reviews")
    op.drop_table("work_order_status_history")
    op.drop_table("work_orders")
    op.drop_table("occurrences")
