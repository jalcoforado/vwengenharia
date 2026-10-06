from datetime import datetime
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


class IntegrationEnvelope(BaseModel):
    schema_version: str = "1"
    tenant_id: UUID
    generated_at: datetime
    items: list[dict[str, Any]]
