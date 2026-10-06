from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.operations import AssetStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    document: str | None = Field(default=None, max_length=32)
    contact_name: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    document: str | None = Field(default=None, max_length=32)
    contact_name: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None


class ClientRead(ORMModel):
    id: UUID
    name: str
    document: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DevelopmentCreate(BaseModel):
    client_id: UUID
    name: str = Field(min_length=2, max_length=200)
    address_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=12)


class DevelopmentUpdate(BaseModel):
    client_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=200)
    address_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=12)
    is_active: bool | None = None


class DevelopmentRead(ORMModel):
    id: UUID
    client_id: UUID
    name: str
    address_line: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StationCreate(BaseModel):
    development_id: UUID
    name: str = Field(min_length=2, max_length=200)
    code: str | None = Field(default=None, max_length=80)
    station_type: str | None = Field(default=None, max_length=80)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    visit_frequency_days: int | None = Field(default=None, ge=1, le=365)


class StationUpdate(BaseModel):
    development_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=200)
    code: str | None = Field(default=None, max_length=80)
    station_type: str | None = Field(default=None, max_length=80)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    visit_frequency_days: int | None = Field(default=None, ge=1, le=365)
    is_active: bool | None = None


class StationRead(ORMModel):
    id: UUID
    development_id: UUID
    name: str
    code: str | None
    station_type: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    visit_frequency_days: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssetTypeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str | None = Field(default=None, max_length=60)


class AssetTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, max_length=60)
    is_active: bool | None = None


class AssetTypeRead(ORMModel):
    id: UUID
    name: str
    code: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssetCreate(BaseModel):
    station_id: UUID
    asset_type_id: UUID
    name: str = Field(min_length=2, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    installed_at: date | None = None
    status: AssetStatus = AssetStatus.OPERANDO
    notes: str | None = None


class AssetUpdate(BaseModel):
    station_id: UUID | None = None
    asset_type_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    installed_at: date | None = None
    status: AssetStatus | None = None
    notes: str | None = None
    is_active: bool | None = None


class AssetRead(ORMModel):
    id: UUID
    station_id: UUID
    asset_type_id: UUID
    name: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    installed_at: date | None
    status: str
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
