from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.models.identity import Role
from app.modules.audit.schemas import AuditEventRead
from app.modules.audit.service import list_audit_events
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles

router = APIRouter(tags=["auditoria"])

AUDIT_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
)
AuditContextDep = Annotated[AuthContext, Depends(require_roles(*AUDIT_ROLES))]
PageLimit = Annotated[int, Query(ge=1, le=500)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("/audit-events", response_model=list[AuditEventRead])
async def get_audit_events(
    context: AuditContextDep,
    session: SessionDep,
    action: str | None = None,
    entity_type: str | None = None,
    actor_user_id: UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: PageLimit = 200,
    offset: PageOffset = 0,
) -> list:
    return await list_audit_events(
        session,
        context,
        action=action,
        entity_type=entity_type,
        actor_user_id=actor_user_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        limit=limit,
        offset=offset,
    )
