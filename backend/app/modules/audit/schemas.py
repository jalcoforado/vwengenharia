from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    event_metadata: dict[str, Any]
    occurred_at: datetime
