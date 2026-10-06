from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InboxItem(BaseModel):
    kind: str
    priority: str
    title: str
    message: str
    entity_type: str
    entity_id: UUID
    due_at: datetime | None = None
    status: str
