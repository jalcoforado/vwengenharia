from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Role
from app.models.maintenance import WorkOrder
from app.models.materials import (
    InventoryItem,
    InventoryMovement,
    InventoryMovementType,
    MaterialRequest,
    RequestCategory,
    RequestStatus,
)
from app.models.operations import Asset, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit, tenant_get_or_404
from app.modules.field.service import get_accessible_visit
from app.modules.materials.schemas import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryMovementCreate,
    MaterialRequestCreate,
    MaterialRequestIssue,
    MaterialRequestUpdate,
)
from app.modules.operations.service import get_accessible_work_order

FIELD_ROLES = {Role.TECNICO.value, Role.MANUTENCAO.value}
MANAGEMENT_ROLES = {
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
}
POSITIVE_MOVEMENTS = {
    InventoryMovementType.ENTRADA.value,
    InventoryMovementType.AJUSTE_POSITIVO.value,
}


def _ensure_management(context: AuthContext) -> None:
    if context.membership.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="management_role_required",
        )


async def _locked_inventory_item(
    session: AsyncSession,
    tenant_id: UUID,
    item_id: UUID,
) -> InventoryItem:
    item = (
        await session.execute(
            select(InventoryItem)
            .where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.id == item_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="inventory_item_not_found",
        )
    return item


async def create_inventory_item(
    session: AsyncSession,
    context: AuthContext,
    payload: InventoryItemCreate,
) -> InventoryItem:
    _ensure_management(context)
    code = payload.code.strip().upper()
    existing = (
        await session.execute(
            select(InventoryItem.id).where(
                InventoryItem.tenant_id == context.tenant.id,
                InventoryItem.code == code,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="inventory_item_code_exists",
        )

    item = InventoryItem(
        tenant_id=context.tenant.id,
        code=code,
        name=payload.name.strip(),
        unit=payload.unit.strip(),
        current_quantity=Decimal("0"),
        minimum_quantity=payload.minimum_quantity,
        notes=payload.notes.strip() if payload.notes else None,
        is_active=True,
    )
    session.add(item)
    await session.flush()
    add_audit(
        session,
        context,
        action="INVENTORY_ITEM_CREATE",
        entity_type="inventory_item",
        entity_id=item.id,
    )
    await session.commit()
    await session.refresh(item)
    return item


async def list_inventory_items(
    session: AsyncSession,
    context: AuthContext,
    *,
    active_only: bool = True,
    low_stock_only: bool = False,
) -> list[InventoryItem]:
    stmt = select(InventoryItem).where(
        InventoryItem.tenant_id == context.tenant.id
    )
    if active_only:
        stmt = stmt.where(InventoryItem.is_active.is_(True))
    if low_stock_only:
        stmt = stmt.where(
            InventoryItem.current_quantity <= InventoryItem.minimum_quantity
        )
    stmt = stmt.order_by(InventoryItem.name)
    return list((await session.execute(stmt)).scalars().all())


async def update_inventory_item(
    session: AsyncSession,
    context: AuthContext,
    item_id: UUID,
    payload: InventoryItemUpdate,
) -> InventoryItem:
    _ensure_management(context)
    item = await tenant_get_or_404(
        session, InventoryItem, context.tenant.id, item_id
    )
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(item, field, value)

    add_audit(
        session,
        context,
        action="INVENTORY_ITEM_UPDATE",
        entity_type="inventory_item",
        entity_id=item.id,
        fields=sorted(changes.keys()),
    )
    await session.commit()
    await session.refresh(item)
    return item


async def create_inventory_movement(
    session: AsyncSession,
    context: AuthContext,
    payload: InventoryMovementCreate,
) -> InventoryMovement:
    _ensure_management(context)
    item = await _locked_inventory_item(
        session, context.tenant.id, payload.inventory_item_id
    )
    if not item.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="inventory_item_inactive",
        )

    if payload.station_id is not None:
        await tenant_get_or_404(
            session, Station, context.tenant.id, payload.station_id
        )
    if payload.work_order_id is not None:
        await tenant_get_or_404(
            session, WorkOrder, context.tenant.id, payload.work_order_id
        )
    if payload.material_request_id is not None:
        await tenant_get_or_404(
            session,
            MaterialRequest,
            context.tenant.id,
            payload.material_request_id,
        )

    direction = (
        Decimal("1")
        if payload.movement_type.value in POSITIVE_MOVEMENTS
        else Decimal("-1")
    )
    balance_after = item.current_quantity + direction * payload.quantity
    if balance_after < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="insufficient_inventory",
        )

    item.current_quantity = balance_after
    movement = InventoryMovement(
        tenant_id=context.tenant.id,
        inventory_item_id=item.id,
        performed_by_user_id=context.user.id,
        movement_type=payload.movement_type.value,
        quantity=payload.quantity,
        balance_after=balance_after,
        unit_cost=payload.unit_cost,
        station_id=payload.station_id,
        work_order_id=payload.work_order_id,
        material_request_id=payload.material_request_id,
        occurred_at=payload.occurred_at,
        notes=payload.notes.strip() if payload.notes else None,
    )
    session.add(movement)
    await session.flush()
    add_audit(
        session,
        context,
        action="INVENTORY_MOVEMENT_CREATE",
        entity_type="inventory_movement",
        entity_id=movement.id,
        fields=[
            f"type:{movement.movement_type}",
            f"quantity:{movement.quantity}",
            f"balance_after:{movement.balance_after}",
        ],
    )
    await session.commit()
    await session.refresh(movement)
    return movement


async def list_inventory_movements(
    session: AsyncSession,
    context: AuthContext,
    *,
    item_id: UUID | None = None,
    limit: int = 200,
) -> list[InventoryMovement]:
    stmt = select(InventoryMovement).where(
        InventoryMovement.tenant_id == context.tenant.id
    )
    if item_id is not None:
        stmt = stmt.where(InventoryMovement.inventory_item_id == item_id)
    stmt = stmt.order_by(
        InventoryMovement.occurred_at.desc(),
        InventoryMovement.created_at.desc(),
    ).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def inventory_summary(
    session: AsyncSession,
    context: AuthContext,
) -> dict[str, int | Decimal]:
    tenant_id = context.tenant.id
    active_items = await session.scalar(
        select(func.count(InventoryItem.id)).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.is_active.is_(True),
        )
    )
    low_stock_items = await session.scalar(
        select(func.count(InventoryItem.id)).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.is_active.is_(True),
            InventoryItem.current_quantity <= InventoryItem.minimum_quantity,
        )
    )
    zero_stock_items = await session.scalar(
        select(func.count(InventoryItem.id)).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.is_active.is_(True),
            InventoryItem.current_quantity <= 0,
        )
    )
    total_quantity = await session.scalar(
        select(func.coalesce(func.sum(InventoryItem.current_quantity), 0)).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.is_active.is_(True),
        )
    )
    return {
        "active_items": int(active_items or 0),
        "low_stock_items": int(low_stock_items or 0),
        "zero_stock_items": int(zero_stock_items or 0),
        "total_quantity": Decimal(total_quantity or 0),
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

    if payload.inventory_item_id is not None:
        inventory_item = await tenant_get_or_404(
            session,
            InventoryItem,
            context.tenant.id,
            payload.inventory_item_id,
        )
        if not inventory_item.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="inventory_item_inactive",
            )

    request = MaterialRequest(
        tenant_id=context.tenant.id,
        station_id=station.id,
        visit_id=payload.visit_id,
        work_order_id=payload.work_order_id,
        asset_id=payload.asset_id,
        inventory_item_id=payload.inventory_item_id,
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
    stmt = stmt.order_by(MaterialRequest.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_material_request(
    session: AsyncSession,
    context: AuthContext,
    request_id: UUID,
    payload: MaterialRequestUpdate,
) -> MaterialRequest:
    _ensure_management(context)
    request = await tenant_get_or_404(
        session, MaterialRequest, context.tenant.id, request_id
    )
    changes = payload.model_dump(exclude_unset=True)

    inventory_item_id = changes.get("inventory_item_id")
    if inventory_item_id is not None:
        await tenant_get_or_404(
            session,
            InventoryItem,
            context.tenant.id,
            inventory_item_id,
        )

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


async def issue_material_request(
    session: AsyncSession,
    context: AuthContext,
    request_id: UUID,
    payload: MaterialRequestIssue,
) -> InventoryMovement:
    _ensure_management(context)
    request = await tenant_get_or_404(
        session, MaterialRequest, context.tenant.id, request_id
    )
    if request.category != RequestCategory.MATERIAL.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="request_is_not_material",
        )
    if request.status in {
        RequestStatus.ATENDIDA.value,
        RequestStatus.CANCELADA.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="request_already_closed",
        )

    item = await _locked_inventory_item(
        session, context.tenant.id, payload.inventory_item_id
    )
    quantity = payload.quantity or request.quantity
    if quantity is None or quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="issue_quantity_required",
        )
    balance_after = item.current_quantity - quantity
    if balance_after < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="insufficient_inventory",
        )

    item.current_quantity = balance_after
    request.inventory_item_id = item.id
    request.status = RequestStatus.ATENDIDA.value

    movement = InventoryMovement(
        tenant_id=context.tenant.id,
        inventory_item_id=item.id,
        performed_by_user_id=context.user.id,
        movement_type=InventoryMovementType.SAIDA.value,
        quantity=quantity,
        balance_after=balance_after,
        station_id=request.station_id,
        work_order_id=request.work_order_id,
        material_request_id=request.id,
        occurred_at=datetime.now(UTC),
        notes=payload.notes.strip() if payload.notes else "Baixa por solicitacao atendida.",
    )
    session.add(movement)
    await session.flush()
    add_audit(
        session,
        context,
        action="MATERIAL_REQUEST_ISSUE",
        entity_type="material_request",
        entity_id=request.id,
        fields=[
            f"inventory_item_id:{item.id}",
            f"quantity:{quantity}",
            f"balance_after:{balance_after}",
        ],
    )
    await session.commit()
    await session.refresh(movement)
    return movement
