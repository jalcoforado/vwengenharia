from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.materials import (
    InventoryMovementType,
    RequestCategory,
    RequestPriority,
    RequestStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InventoryItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=200)
    unit: str = Field(min_length=1, max_length=40)
    minimum_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = Field(default=None, max_length=5000)


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    minimum_quantity: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None


class InventoryItemRead(ORMModel):
    id: UUID
    code: str
    name: str
    unit: str
    current_quantity: Decimal
    minimum_quantity: Decimal
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InventoryMovementCreate(BaseModel):
    inventory_item_id: UUID
    movement_type: InventoryMovementType
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    station_id: UUID | None = None
    work_order_id: UUID | None = None
    material_request_id: UUID | None = None
    occurred_at: datetime
    notes: str | None = Field(default=None, max_length=5000)


class InventoryMovementRead(ORMModel):
    id: UUID
    inventory_item_id: UUID
    performed_by_user_id: UUID
    movement_type: str
    quantity: Decimal
    balance_after: Decimal
    unit_cost: Decimal | None
    station_id: UUID | None
    work_order_id: UUID | None
    material_request_id: UUID | None
    occurred_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime


class InventorySummary(BaseModel):
    active_items: int
    low_stock_items: int
    zero_stock_items: int
    total_quantity: Decimal


class MaterialRequestCreate(BaseModel):
    station_id: UUID
    visit_id: UUID | None = None
    work_order_id: UUID | None = None
    asset_id: UUID | None = None
    inventory_item_id: UUID | None = None
    category: RequestCategory = RequestCategory.MATERIAL
    item_name: str = Field(min_length=2, max_length=200)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=40)
    priority: RequestPriority = RequestPriority.MEDIA
    needed_by: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class MaterialRequestUpdate(BaseModel):
    inventory_item_id: UUID | None = None
    status: RequestStatus | None = None
    priority: RequestPriority | None = None
    needed_by: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class MaterialRequestIssue(BaseModel):
    inventory_item_id: UUID
    quantity: Decimal | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=5000)


class MaterialRequestRead(ORMModel):
    id: UUID
    station_id: UUID
    visit_id: UUID | None
    work_order_id: UUID | None
    asset_id: UUID | None
    inventory_item_id: UUID | None
    requested_by_user_id: UUID
    category: str
    item_name: str
    quantity: Decimal | None
    unit: str | None
    priority: str
    status: str
    needed_by: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
