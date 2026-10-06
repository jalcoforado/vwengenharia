from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.modules.auth.dependencies import AuthContext


async def list_audit_events(
    session: AsyncSession,
    context: AuthContext,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    actor_user_id: UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(AuditEvent.tenant_id == context.tenant.id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if actor_user_id:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
    if occurred_from:
        stmt = stmt.where(AuditEvent.occurred_at >= occurred_from)
    if occurred_to:
        stmt = stmt.where(AuditEvent.occurred_at <= occurred_to)
    stmt = stmt.order_by(AuditEvent.occurred_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())
