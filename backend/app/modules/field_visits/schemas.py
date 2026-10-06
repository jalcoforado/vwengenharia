from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.field import ChecklistItemType, MeasurementStatus, VisitStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ChecklistItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=2, max_length=220)
    item_type: ChecklistItemType
    required: bool = False
    sort_order: int = Field(default=0, ge=0)
    config: dict[str, Any] = Field(default_factory=dict)


class ChecklistTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    station_type: str | None = Field(default=None, max_length=80)
    version: int = Field(default=1, ge=1)
    items: list[ChecklistItemCreate] = Field(min_length=1)


class ChecklistItemRead(ORMModel):
    id: UUID
    code: str
    label: str
    item_type: str
    required: bool
    sort_order: int
    config: dict[str, Any]


class ChecklistTemplateRead(ORMModel):
    id: UUID
    name: str
    station_type: str | None
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChecklistTemplateDetail(ChecklistTemplateRead):
    items: list[ChecklistItemRead]


class VisitCreate(BaseModel):
    station_id: UUID
    assigned_user_id: UUID
    checklist_template_id: UUID
    scheduled_for: datetime


class VisitRead(ORMModel):
    id: UUID
    station_id: UUID
    assigned_user_id: UUID
    checklist_template_id: UUID
    scheduled_for: datetime
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    notes: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


class ClientOperation(BaseModel):
    client_operation_id: UUID


class VisitStartRequest(ClientOperation):
    pass


class VisitFinishRequest(ClientOperation):
    notes: str | None = None


class VisitAnswerInput(BaseModel):
    item_id: UUID
    value: dict[str, Any]
    note: str | None = None


class VisitAnswersRequest(ClientOperation):
    answers: list[VisitAnswerInput] = Field(min_length=1)


class MeasurementInput(BaseModel):
    measurement_type: str = Field(min_length=1, max_length=80)
    status: MeasurementStatus
    value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=40)
    reason: str | None = Field(default=None, max_length=255)
    taken_at: datetime

    @model_validator(mode="after")
    def validate_measurement_semantics(self) -> "MeasurementInput":
        if self.status == MeasurementStatus.MEDIDO and self.value is None:
            raise ValueError("value is required when status=MEDIDO")
        if self.status != MeasurementStatus.MEDIDO and self.value is not None:
            raise ValueError("value must be null when measurement was not measured")
        if self.status == MeasurementStatus.NAO_MEDIDO and not self.reason:
            raise ValueError("reason is required when status=NAO_MEDIDO")
        return self


class MeasurementsRequest(ClientOperation):
    measurements: list[MeasurementInput] = Field(min_length=1)


class MeasurementRead(ORMModel):
    id: UUID
    visit_id: UUID
    measurement_type: str
    status: str
    value: Decimal | None
    unit: str | None
    reason: str | None
    taken_at: datetime


class SyncAck(BaseModel):
    client_operation_id: UUID
    duplicate: bool
    entity_id: UUID
    action: str


class VisitStatusFilter(BaseModel):
    status: VisitStatus | None = None
