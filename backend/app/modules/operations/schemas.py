from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.maintenance import (
    OccurrenceSeverity,
    ReviewDecision,
    WorkOrderPriority,
    WorkOrderStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OccurrenceCreate(BaseModel):
    visit_id: UUID | None = None
    station_id: UUID
    asset_id: UUID | None = None
    occurrence_type: str = Field(min_length=2, max_length=100)
    severity: OccurrenceSeverity
    description: str = Field(min_length=3, max_length=5000)
    detected_at: datetime


class OccurrenceRead(ORMModel):
    id: UUID
    visit_id: UUID | None
    station_id: UUID
    asset_id: UUID | None
    occurrence_type: str
    severity: str
    status: str
    description: str
    detected_at: datetime
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class WorkOrderCreate(BaseModel):
    occurrence_id: UUID | None = None
    station_id: UUID | None = None
    asset_id: UUID | None = None
    assigned_membership_id: UUID | None = None
    priority: WorkOrderPriority
    description: str = Field(min_length=3, max_length=5000)


class WorkOrderAssign(BaseModel):
    assigned_membership_id: UUID | None


class WorkOrderTransition(BaseModel):
    status: WorkOrderStatus
    note: str | None = Field(default=None, max_length=500)


class WorkOrderRead(ORMModel):
    id: UUID
    occurrence_id: UUID | None
    station_id: UUID
    asset_id: UUID | None
    assigned_membership_id: UUID | None
    priority: str
    status: str
    description: str
    sla_due_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkOrderHistoryRead(ORMModel):
    id: UUID
    work_order_id: UUID
    from_status: str | None
    to_status: str
    changed_by_user_id: UUID
    note: str | None
    changed_at: datetime


class VisitReviewCreate(BaseModel):
    decision: ReviewDecision
    notes: str | None = Field(default=None, max_length=2000)


class VisitReviewRead(ORMModel):
    id: UUID
    visit_id: UUID
    reviewer_user_id: UUID
    decision: str
    notes: str | None
    reviewed_at: datetime


class DashboardOverview(BaseModel):
    active_stations: int
    unavailable_assets: int
    visits_waiting_review: int
    open_occurrences: int
    open_work_orders: int
    overdue_work_orders: int
    critical_work_orders: int


class SlaBucket(BaseModel):
    priority: str
    open_count: int
    overdue_count: int


class DashboardSla(BaseModel):
    buckets: list[SlaBucket]
