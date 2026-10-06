from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LegacyVisitStage(TimestampMixin, Base):
    __tablename__ = "legacy_visit_staging"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_legacy_visit_fingerprint"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    station_label: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    technician_label: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="STAGED", index=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_visit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )


class LegacyStationMapping(TimestampMixin, Base):
    __tablename__ = "legacy_station_mappings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_label", name="uq_legacy_station_label"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )


class LegacyTechnicianMapping(TimestampMixin, Base):
    __tablename__ = "legacy_technician_mappings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_label", name="uq_legacy_technician_label"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
