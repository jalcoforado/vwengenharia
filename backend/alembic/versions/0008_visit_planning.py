"""recurring visit planning

Revision ID: 0008_visit_planning
Revises: 0007_drop_ai_runs
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_visit_planning"
down_revision: str | None = "0007_drop_ai_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visit_plans",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("technician_membership_id", sa.Uuid(), nullable=False),
        sa.Column("checklist_template_id", sa.Uuid(), nullable=True),
        sa.Column("frequency_days", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["stations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["technician_membership_id"], ["memberships.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["checklist_template_id"], ["checklist_templates.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_visit_plans_tenant_id", "visit_plans", ["tenant_id"])
    op.create_index("ix_visit_plans_station_id", "visit_plans", ["station_id"])
    op.create_index(
        "ix_visit_plans_technician_membership_id",
        "visit_plans",
        ["technician_membership_id"],
    )
    op.create_index(
        "ix_visit_plans_checklist_template_id",
        "visit_plans",
        ["checklist_template_id"],
    )
    op.create_index("ix_visit_plans_next_due_at", "visit_plans", ["next_due_at"])

    op.add_column("visits", sa.Column("visit_plan_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_visits_visit_plan_id",
        "visits",
        "visit_plans",
        ["visit_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_visits_visit_plan_id", "visits", ["visit_plan_id"])
    op.create_unique_constraint(
        "uq_visit_plan_schedule",
        "visits",
        ["tenant_id", "visit_plan_id", "scheduled_for"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_visit_plan_schedule", "visits", type_="unique")
    op.drop_index("ix_visits_visit_plan_id", table_name="visits")
    op.drop_constraint("fk_visits_visit_plan_id", "visits", type_="foreignkey")
    op.drop_column("visits", "visit_plan_id")
    op.drop_table("visit_plans")
