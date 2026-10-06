"""field visits

Revision ID: 0003_field_visits
Revises: 0002_core_registers
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_field_visits"
down_revision: str | None = "0002_core_registers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checklist_templates",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("station_type", sa.String(length=80), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "name",
            "version",
            name="uq_checklist_templates_tenant_name_version",
        ),
    )
    op.create_index("ix_checklist_templates_tenant_id", "checklist_templates", ["tenant_id"])

    op.create_table(
        "checklist_template_items",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=220), nullable=False),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"], ["checklist_templates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "template_id", "code", name="uq_checklist_item_template_code"
        ),
    )
    op.create_index(
        "ix_checklist_template_items_tenant_id",
        "checklist_template_items",
        ["tenant_id"],
    )
    op.create_index(
        "ix_checklist_template_items_template_id",
        "checklist_template_items",
        ["template_id"],
    )

    op.create_table(
        "visits",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=False),
        sa.Column("checklist_template_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["checklist_template_id"], ["checklist_templates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_visits_tenant_id", "visits", ["tenant_id"])
    op.create_index("ix_visits_station_id", "visits", ["station_id"])
    op.create_index("ix_visits_assigned_user_id", "visits", ["assigned_user_id"])
    op.create_index(
        "ix_visits_checklist_template_id", "visits", ["checklist_template_id"]
    )
    op.create_index("ix_visits_scheduled_for", "visits", ["scheduled_for"])
    op.create_index("ix_visits_status", "visits", ["status"])

    op.create_table(
        "visit_answers",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["checklist_template_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("visit_id", "item_id", name="uq_visit_answer_visit_item"),
    )
    op.create_index("ix_visit_answers_tenant_id", "visit_answers", ["tenant_id"])
    op.create_index("ix_visit_answers_visit_id", "visit_answers", ["visit_id"])
    op.create_index("ix_visit_answers_item_id", "visit_answers", ["item_id"])

    op.create_table(
        "measurements",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("measurement_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("value", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_measurements_tenant_id", "measurements", ["tenant_id"])
    op.create_index("ix_measurements_visit_id", "measurements", ["visit_id"])
    op.create_index(
        "ix_measurements_measurement_type", "measurements", ["measurement_type"]
    )

    op.create_table(
        "operation_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("client_operation_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "client_operation_id",
            name="uq_operation_receipt_tenant_client_op",
        ),
    )
    op.create_index(
        "ix_operation_receipts_tenant_id", "operation_receipts", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_table("operation_receipts")
    op.drop_table("measurements")
    op.drop_table("visit_answers")
    op.drop_table("visits")
    op.drop_table("checklist_template_items")
    op.drop_table("checklist_templates")
