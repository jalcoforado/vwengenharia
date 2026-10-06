from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.field import AnswerType, MeasurementStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ChecklistTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    version: int = Field(default=1, ge=1, le=999)


class ChecklistTemplateRead(ORMModel):
    id: UUID
    name: str
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChecklistItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_\-]+$")
    label: str = Field(min_length=2, max_length=200)
    answer_type: AnswerType
    required: bool = False
    position: int = Field(default=0, ge=0, le=10000)
    options_json: list[str] | None = None
    asset_type_id: UUID | None = None


class ChecklistItemRead(ORMModel):
    id: UUID
    template_id: UUID
    code: str
    label: str
    answer_type: str
    required: bool
    position: int
    options_json: list | None
    asset_type_id: UUID | None
    created_at: datetime
    updated_at: datetime


class VisitCreate(BaseModel):
    station_id: UUID
    technician_membership_id: UUID
    checklist_template_id: UUID | None = None
    scheduled_for: datetime
    notes: str | None = Field(default=None, max_length=4000)
    client_operation_id: UUID | None = None


class VisitRead(ORMModel):
    id: UUID
    station_id: UUID
    technician_membership_id: UUID
    checklist_template_id: UUID | None
    scheduled_for: datetime
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class VisitCommand(BaseModel):
    client_operation_id: UUID


class VisitAnswerUpsert(BaseModel):
    item_id: UUID
    value: Any
    client_operation_id: UUID | None = None


class VisitAnswerRead(ORMModel):
    id: UUID
    visit_id: UUID
    item_id: UUID
    value_json: Any
    created_at: datetime
    updated_at: datetime


class MeasurementCreate(BaseModel):
    measurement_type: str = Field(min_length=1, max_length=80)
    status: MeasurementStatus
    value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=40)
    reason: str | None = Field(default=None, max_length=255)
    measured_at: datetime
    client_operation_id: UUID | None = None

    @model_validator(mode="after")
    def validate_measurement(self) -> "MeasurementCreate":
        if self.status == MeasurementStatus.MEASURED:
            if self.value is None:
                raise ValueError("value is required when status is MEASURED")
            if self.reason is not None:
                raise ValueError("reason must be empty when status is MEASURED")
        else:
            if self.value is not None:
                raise ValueError("value must be empty when status is NOT_MEASURED")
            if not self.reason:
                raise ValueError("reason is required when status is NOT_MEASURED")
        return self


class MeasurementRead(ORMModel):
    id: UUID
    visit_id: UUID
    measurement_type: str
    status: str
    value: Decimal | None
    unit: str | None
    reason: str | None
    measured_at: datetime
    created_at: datetime
    updated_at: datetime


class AttachmentRegisterCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=180)
    content_type: str = Field(min_length=3, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0, le=50_000_000)
    asset_id: UUID | None = None
    caption: str | None = Field(default=None, max_length=255)
    client_operation_id: UUID | None = None


class AttachmentRead(ORMModel):
    id: UUID
    visit_id: UUID
    asset_id: UUID | None
    object_key: str
    content_type: str
    size_bytes: int | None
    storage_status: str
    uploaded_at: datetime | None
    caption: str | None
    created_at: datetime
    updated_at: datetime


class BootstrapStation(ORMModel):
    id: UUID
    name: str
    code: str | None
    station_type: str | None


class BootstrapAsset(ORMModel):
    id: UUID
    station_id: UUID
    asset_type_id: UUID
    name: str
    status: str


class FieldBootstrapResponse(BaseModel):
    generated_at: datetime
    visits: list[VisitRead]
    stations: list[BootstrapStation]
    assets: list[BootstrapAsset]
    templates: list[ChecklistTemplateRead]
    items: list[ChecklistItemRead]
    answers: list[VisitAnswerRead]
    measurements: list[MeasurementRead]
    attachments: list[AttachmentRead]


class AttachmentPresignResponse(BaseModel):
    attachment: AttachmentRead
    upload_url: str
    expires_in: int
    required_headers: dict[str, str]
