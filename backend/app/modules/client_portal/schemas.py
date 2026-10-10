from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ClientPortalStation(BaseModel):
    id: UUID
    development_id: UUID
    development_name: str
    name: str
    code: str | None
    station_type: str | None


class ClientPortalVisit(BaseModel):
    id: UUID
    station_id: UUID
    scheduled_for: datetime
    finished_at: datetime | None
    status: str


class ClientPortalOccurrence(BaseModel):
    id: UUID
    station_id: UUID
    occurrence_type: str
    severity: str
    status: str
    description: str
    detected_at: datetime


class ClientPortalWorkOrder(BaseModel):
    id: UUID
    station_id: UUID
    asset_id: UUID | None
    priority: str
    status: str
    description: str
    sla_due_at: datetime
    completed_at: datetime | None


class ClientPortalClient(BaseModel):
    id: UUID
    name: str


class ClientPortalResponse(BaseModel):
    clients: list[ClientPortalClient]
    stations: list[ClientPortalStation]
    visits: list[ClientPortalVisit]
    occurrences: list[ClientPortalOccurrence]
    work_orders: list[ClientPortalWorkOrder]



class ClientAccessCreate(BaseModel):
    membership_id: UUID
    client_id: UUID


class ClientAccessRead(BaseModel):
    id: UUID
    membership_id: UUID
    client_id: UUID
    user_name: str | None = None
    user_email: str | None = None


class ClientPortalCredentialCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
