import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RequestCategory(str, enum.Enum):
    MATERIAL = "MATERIAL"
    SERVICO = "SERVICO"
    TERCEIRO = "TERCEIRO"


class RequestPriority(str, enum.Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


class RequestStatus(str, enum.Enum):
    SOLICITADA = "SOLICITADA"
    APROVADA = "APROVADA"
    EM_COMPRA = "EM_COMPRA"
    AGUARDANDO_TERCEIRO = "AGUARDANDO_TERCEIRO"
    ATENDIDA = "ATENDIDA"
    CANCELADA = "CANCELADA"


class InventoryMovementType(str, enum.Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    AJUSTE_POSITIVO = "AJUSTE_POSITIVO"
    AJUSTE_NEGATIVO = "AJUSTE_NEGATIVO"


class InventoryItem(TimestampMixin, Base):
    __tablename__ = "inventory_items"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    current_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
    minimum_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class InventoryMovement(TimestampMixin, Base):
    __tablename__ = "inventory_movements"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inventory_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    performed_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    station_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    work_order_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    material_request_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("material_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MaterialRequest(TimestampMixin, Base):
    __tablename__ = "material_requests"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    visit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("visits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    work_order_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    inventory_item_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
