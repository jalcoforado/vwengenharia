from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.materials import RequestCategory, RequestPriority, RequestStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MaterialRequestCreate(BaseModel):
    station_id: UUID
    visit_id: UUID | None = None
    work_order_id: UUID | None = None
    asset_id: UUID | None = None
    category: RequestCategory = RequestCategory.MATERIAL
    item_name: str = Field(min_length=2, max_length=200)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=40)
    priority: RequestPriority = RequestPriority.MEDIA
    needed_by: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class MaterialRequestUpdate(BaseModel):
    status: RequestStatus | None = None
    priority: RequestPriority | None = None
    needed_by: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class MaterialRequestRead(ORMModel):
    id: UUID
    station_id: UUID
    visit_id: UUID | None
    work_order_id: UUID | None
    asset_id: UUID | None
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
