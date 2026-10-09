from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.operations import AssetStatus, ContactScope


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    document: str | None = Field(default=None, max_length=32)
    contact_name: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_role: str | None = Field(default=None, max_length=120)
    contact_whatsapp: str | None = Field(default=None, max_length=40)


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    document: str | None = Field(default=None, max_length=32)
    contact_name: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_role: str | None = Field(default=None, max_length=120)
    contact_whatsapp: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None


class ClientRead(ORMModel):
    id: UUID
    name: str
    document: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    contact_role: str | None
    contact_whatsapp: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientContactCreate(BaseModel):
    client_id: UUID
    development_id: UUID
    scope: ContactScope
    portal_access: bool = False


class ClientContactUpdate(BaseModel):
    scope: ContactScope | None = None
    portal_access: bool | None = None
    is_active: bool | None = None


class ClientContactRead(ORMModel):
    id: UUID
    client_id: UUID
    development_id: UUID
    scope: ContactScope
    is_primary: bool
    portal_access: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DevelopmentCreate(BaseModel):
    client_id: UUID
    name: str = Field(min_length=2, max_length=200)
    document: str | None = Field(default=None, max_length=32)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None
    address_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=12)
    development_type: str | None = Field(default=None, max_length=60)
    address_number: str | None = Field(default=None, max_length=20)
    address_complement: str | None = Field(default=None, max_length=120)
    address_district: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    units_count: int | None = Field(default=None, ge=0, le=1_000_000)
    access_hours: str | None = Field(default=None, max_length=255)


class DevelopmentUpdate(BaseModel):
    client_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=200)
    document: str | None = Field(default=None, max_length=32)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None
    address_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=12)
    development_type: str | None = Field(default=None, max_length=60)
    address_number: str | None = Field(default=None, max_length=20)
    address_complement: str | None = Field(default=None, max_length=120)
    address_district: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    units_count: int | None = Field(default=None, ge=0, le=1_000_000)
    access_hours: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class DevelopmentRead(ORMModel):
    id: UUID
    client_id: UUID
    name: str
    document: str | None
    contact_phone: str | None
    contact_email: str | None
    address_line: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    development_type: str | None
    address_number: str | None
    address_complement: str | None
    address_district: str | None
    latitude: float | None
    longitude: float | None
    units_count: int | None
    access_hours: str | None
    has_facade_photo: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FacadePhotoPresign(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=100)
    size_bytes: int = Field(gt=0)


class FacadePhotoUpload(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int
    required_headers: dict[str, str]


class FacadePhotoComplete(BaseModel):
    object_key: str = Field(min_length=1, max_length=512)


class FacadePhotoUrl(BaseModel):
    url: str
    expires_in: int


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
