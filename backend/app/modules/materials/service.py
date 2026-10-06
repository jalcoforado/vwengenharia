from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import Visit
from app.models.identity import Role
from app.models.maintenance import WorkOrder
from app.models.materials import MaterialRequest, RequestStatus
from app.models.operations import Asset, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit, tenant_get_or_404
from app.modules.field.service import get_accessible_visit
from app.modules.materials.schemas import MaterialRequestCreate, MaterialRequestUpdate
from app.modules.operations.service import get_accessible_work_order

FIELD_ROLES = {Role.TECNICO.value, Role.MANUTENCAO.value}
MANAGEMENT_ROLES = {
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
}


async def create_material_request(
    session: AsyncSession,
    context: AuthContext,
    payload: MaterialRequestCreate,
) -> MaterialRequest:
    station = await tenant_get_or_404(
        session, Station, context.tenant.id, payload.station_id
    )

    if payload.visit_id is not None:
        visit = await get_accessible_visit(session, context, payload.visit_id)
        if visit.station_id != station.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="visit_station_mismatch",
            )
    elif context.membership.role in FIELD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="field_request_requires_visit",
        )

    if payload.work_order_id is not None:
        work_order = await get_accessible_work_order(
            session, context, payload.work_order_id
        )
        if work_order.station_id != station.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="work_order_station_mismatch",
            )

    if payload.asset_id is not None:
        asset = await tenant_get_or_404(
            session, Asset, context.tenant.id, payload.asset_id
        )
        if asset.station_id != station.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="asset_station_mismatch",
            )

    request = MaterialRequest(
        tenant_id=context.tenant.id,
        station_id=station.id,
        visit_id=payload.visit_id,
        work_order_id=payload.work_order_id,
        asset_id=payload.asset_id,
        requested_by_user_id=context.user.id,
        category=payload.category.value,
        item_name=payload.item_name.strip(),
        quantity=payload.quantity,
        unit=payload.unit.strip() if payload.unit else None,
        priority=payload.priority.value,
        status=RequestStatus.SOLICITADA.value,
        needed_by=payload.needed_by,
        notes=payload.notes.strip() if payload.notes else None,
    )
    session.add(request)
    await session.flush()
    add_audit(
        session,
        context,
        action="MATERIAL_REQUEST_CREATE",
        entity_type="material_request",
        entity_id=request.id,
    )
    await session.commit()
    await session.refresh(request)
    return request


async def list_material_requests(
    session: AsyncSession,
    context: AuthContext,
    *,
    request_status: str | None = None,
    station_id: UUID | None = None,
    limit: int = 200,
) -> list[MaterialRequest]:
    stmt = select(MaterialRequest).where(
        MaterialRequest.tenant_id == context.tenant.id
    )
    if context.membership.role in FIELD_ROLES:
        stmt = stmt.where(
            MaterialRequest.requested_by_user_id == context.user.id
        )
    if request_status is not None:
        stmt = stmt.where(MaterialRequest.status == request_status)
    if station_id is not None:
        stmt = stmt.where(MaterialRequest.station_id == station_id)
    stmt = stmt.order_by(
        MaterialRequest.created_at.desc()
    ).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_material_request(
    session: AsyncSession,
    context: AuthContext,
    request_id: UUID,
    payload: MaterialRequestUpdate,
) -> MaterialRequest:
    if context.membership.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="management_role_required",
        )

    request = await tenant_get_or_404(
        session, MaterialRequest, context.tenant.id, request_id
    )
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(request, field, value)

    add_audit(
        session,
        context,
        action="MATERIAL_REQUEST_UPDATE",
        entity_type="material_request",
        entity_id=request.id,
        fields=sorted(changes.keys()),
    )
    await session.commit()
    await session.refresh(request)
    return request
