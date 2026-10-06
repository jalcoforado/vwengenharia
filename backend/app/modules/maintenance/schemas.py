from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.maintenance import MaintenanceType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MaintenancePlanCreate(BaseModel):
    asset_id: UUID
    assigned_membership_id: UUID | None = None
    maintenance_type: MaintenanceType = MaintenanceType.PREVENTIVA
    frequency_days: int = Field(ge=1, le=1095)
    next_due_at: datetime
    instructions: str | None = Field(default=None, max_length=5000)


class MaintenancePlanUpdate(BaseModel):
    assigned_membership_id: UUID | None = None
    frequency_days: int | None = Field(default=None, ge=1, le=1095)
    next_due_at: datetime | None = None
    instructions: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None


class MaintenancePlanRead(ORMModel):
    id: UUID
    asset_id: UUID
    assigned_membership_id: UUID | None
    maintenance_type: str
    frequency_days: int
    next_due_at: datetime
    last_completed_at: datetime | None
    instructions: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MaintenanceExecutionCreate(BaseModel):
    maintenance_plan_id: UUID | None = None
    work_order_id: UUID | None = None
    asset_id: UUID | None = None
    maintenance_type: MaintenanceType | None = None
    started_at: datetime
    completed_at: datetime
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_source(self) -> "MaintenanceExecutionCreate":
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must be after started_at")
        if self.maintenance_plan_id is None and self.asset_id is None:
            raise ValueError("asset_id is required when maintenance_plan_id is absent")
        if self.maintenance_plan_id is None and self.maintenance_type is None:
            raise ValueError("maintenance_type is required when maintenance_plan_id is absent")
        return self


class MaintenanceExecutionRead(ORMModel):
    id: UUID
    maintenance_plan_id: UUID | None
    work_order_id: UUID | None
    asset_id: UUID
    performed_by_membership_id: UUID
    maintenance_type: str
    started_at: datetime
    completed_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime


class MaintenanceSummary(BaseModel):
    active_plans: int
    overdue_plans: int
    due_next_7_days: int
    executions_last_30_days: int
