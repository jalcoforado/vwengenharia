from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IntegrationKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class IntegrationKeyRead(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class IntegrationKeyCreated(IntegrationKeyRead):
    secret: str


class IntegrationResource(StrEnum):
    CLIENTS = "clients"
    DEVELOPMENTS = "developments"
    STATIONS = "stations"
    ASSETS = "assets"
    VISIT_PLANS = "visit-plans"
    VISITS = "visits"
    MEASUREMENTS = "measurements"
    OCCURRENCES = "occurrences"
    WORK_ORDERS = "work-orders"
    WORK_ORDER_HISTORY = "work-order-history"
    REVIEWS = "reviews"
    INVENTORY_ITEMS = "inventory-items"
    INVENTORY_MOVEMENTS = "inventory-movements"


class IntegrationEnvelope(BaseModel):
    schema_version: str = "1"
    tenant_id: UUID
    resource: IntegrationResource
    generated_at: datetime
    offset: int
    limit: int
    next_offset: int | None
    items: list[dict[str, Any]]
