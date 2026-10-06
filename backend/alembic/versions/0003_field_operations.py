"""field operations

Revision ID: 0003_field_operations
Revises: 0002_core_registers
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_field_operations"
down_revision: str | None = "0002_core_registers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checklist_templates",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_checklist_template_version"),
    )
    op.create_index("ix_checklist_templates_tenant_id", "checklist_templates", ["tenant_id"])

    op.create_table(
        "checklist_template_items",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("answer_type", sa.String(length=32), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("asset_type_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_type_id"], ["asset_types.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["checklist_templates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("template_id", "code", name="uq_checklist_item_code"),
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
        sa.Column("technician_membership_id", sa.Uuid(), nullable=False),
        sa.Column("checklist_template_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("client_operation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["checklist_template_id"], ["checklist_templates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["stations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["technician_membership_id"], ["memberships.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "client_operation_id", name="uq_visits_client_operation"
        ),
    )
    op.create_index("ix_visits_tenant_id", "visits", ["tenant_id"])
    op.create_index("ix_visits_station_id", "visits", ["station_id"])
    op.create_index(
        "ix_visits_technician_membership_id",
        "visits",
        ["technician_membership_id"],
    )
    op.create_index(
        "ix_visits_checklist_template_id",
        "visits",
        ["checklist_template_id"],
    )
    op.create_index("ix_visits_scheduled_for", "visits", ["scheduled_for"])

    op.create_table(
        "visit_answers",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("client_operation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["checklist_template_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("visit_id", "item_id", name="uq_visit_answer_item"),
        sa.UniqueConstraint(
            "tenant_id",
            "client_operation_id",
            name="uq_visit_answers_client_operation",
        ),
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
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_operation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "client_operation_id",
            name="uq_measurements_client_operation",
        ),
    )
    op.create_index("ix_measurements_tenant_id", "measurements", ["tenant_id"])
    op.create_index("ix_measurements_visit_id", "measurements", ["visit_id"])
    op.create_index(
        "ix_measurements_measurement_type",
        "measurements",
        ["measurement_type"],
    )

    op.create_table(
        "sync_operations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("client_operation_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "client_operation_id", name="uq_sync_operation"
        ),
    )
    op.create_index("ix_sync_operations_tenant_id", "sync_operations", ["tenant_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("caption", sa.String(length=255), nullable=True),
        sa.Column("client_operation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "object_key", name="uq_attachments_object_key"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "client_operation_id",
            name="uq_attachments_client_operation",
        ),
    )
    op.create_index("ix_attachments_tenant_id", "attachments", ["tenant_id"])
    op.create_index("ix_attachments_visit_id", "attachments", ["visit_id"])
    op.create_index("ix_attachments_asset_id", "attachments", ["asset_id"])


def downgrade() -> None:
    op.drop_table("attachments")
    op.drop_table("sync_operations")
    op.drop_table("measurements")
    op.drop_table("visit_answers")
    op.drop_table("visits")
    op.drop_table("checklist_template_items")
    op.drop_table("checklist_templates")
