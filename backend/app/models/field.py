import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VisitStatus(str, enum.Enum):
    PROGRAMADA = "PROGRAMADA"
    EM_EXECUCAO = "EM_EXECUCAO"
    FINALIZADA = "FINALIZADA"
    AGUARDANDO_REVISAO = "AGUARDANDO_REVISAO"
    REVISADA = "REVISADA"
    DEVOLVIDA = "DEVOLVIDA"
    CANCELADA = "CANCELADA"


class AnswerType(str, enum.Enum):
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    NUMBER = "NUMBER"
    SELECT = "SELECT"
    ASSET_STATUS = "ASSET_STATUS"


class MeasurementStatus(str, enum.Enum):
    MEASURED = "MEASURED"
    NOT_MEASURED = "NOT_MEASURED"


class ChecklistTemplate(TimestampMixin, Base):
    __tablename__ = "checklist_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_checklist_template_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ChecklistTemplateItem(TimestampMixin, Base):
    __tablename__ = "checklist_template_items"
    __table_args__ = (
        UniqueConstraint("template_id", "code", name="uq_checklist_item_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("checklist_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    answer_type: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    options_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    asset_type_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("asset_types.id", ondelete="SET NULL"),
        nullable=True,
    )


class Visit(TimestampMixin, Base):
    __tablename__ = "visits"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_operation_id", name="uq_visits_client_operation"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    technician_membership_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memberships.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    checklist_template_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("checklist_templates.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=VisitStatus.PROGRAMADA.value)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_operation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class VisitAnswer(TimestampMixin, Base):
    __tablename__ = "visit_answers"
    __table_args__ = (
        UniqueConstraint("visit_id", "item_id", name="uq_visit_answer_item"),
        UniqueConstraint("tenant_id", "client_operation_id", name="uq_visit_answers_client_operation"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("checklist_template_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    client_operation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class Measurement(TimestampMixin, Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_operation_id", name="uq_measurements_client_operation"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    measurement_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_operation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "object_key", name="uq_attachments_object_key"),
        UniqueConstraint("tenant_id", "client_operation_id", name="uq_attachments_client_operation"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_operation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
