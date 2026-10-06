"""legacy visit migration staging

Revision ID: 0012_legacy_migration
Revises: 0011_material_requests
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_legacy_migration"
down_revision: str | None = "0011_material_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legacy_visit_staging",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("station_label", sa.String(length=255), nullable=True),
        sa.Column("technician_label", sa.String(length=255), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_status", sa.String(length=80), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("imported_visit_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["imported_visit_id"], ["visits.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "fingerprint", name="uq_legacy_visit_fingerprint"),
    )
    for column in [
        "tenant_id",
        "fingerprint",
        "station_label",
        "technician_label",
        "status",
        "imported_visit_id",
    ]:
        op.create_index(
            f"ix_legacy_visit_staging_{column}",
            "legacy_visit_staging",
            [column],
        )

    op.create_table(
        "legacy_station_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "source_label", name="uq_legacy_station_label"),
    )
    op.create_index(
        "ix_legacy_station_mappings_tenant_id",
        "legacy_station_mappings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_legacy_station_mappings_station_id",
        "legacy_station_mappings",
        ["station_id"],
    )

    op.create_table(
        "legacy_technician_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "source_label", name="uq_legacy_technician_label"),
    )
    op.create_index(
        "ix_legacy_technician_mappings_tenant_id",
        "legacy_technician_mappings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_legacy_technician_mappings_membership_id",
        "legacy_technician_mappings",
        ["membership_id"],
    )


def downgrade() -> None:
    op.drop_table("legacy_technician_mappings")
    op.drop_table("legacy_station_mappings")
    op.drop_table("legacy_visit_staging")
