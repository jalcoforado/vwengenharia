from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.identity import Role
from app.models.materials import InventoryItem, InventoryMovement, MaterialRequest
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.materials.schemas import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMovementCreate,
    InventoryMovementRead,
    InventorySummary,
    MaterialRequestCreate,
    MaterialRequestIssue,
    MaterialRequestRead,
    MaterialRequestUpdate,
)
from app.modules.materials.service import (
    create_inventory_item,
    create_inventory_movement,
    create_material_request,
    inventory_summary,
    issue_material_request,
    list_inventory_items,
    list_inventory_movements,
    list_material_requests,
    update_inventory_item,
    update_material_request,
)

router = APIRouter(tags=["materiais"])

INTERNAL_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
    Role.TECNICO.value,
    Role.MANUTENCAO.value,
)
MANAGEMENT_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
)

ReadContextDep = Annotated[AuthContext, Depends(require_roles(*INTERNAL_ROLES))]
ManagementContextDep = Annotated[AuthContext, Depends(require_roles(*MANAGEMENT_ROLES))]
FieldContextDep = Annotated[AuthContext, Depends(require_roles(*INTERNAL_ROLES))]


@router.get("/inventory/items", response_model=list[InventoryItemRead])
async def get_inventory_items(
    context: ReadContextDep,
    session: SessionDep,
    active_only: bool = True,
    low_stock_only: bool = False,
) -> list[InventoryItem]:
    return await list_inventory_items(
        session,
        context,
        active_only=active_only,
        low_stock_only=low_stock_only,
    )


@router.post(
    "/inventory/items",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_inventory_item(
    payload: InventoryItemCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> InventoryItem:
    return await create_inventory_item(session, context, payload)


@router.patch("/inventory/items/{item_id}", response_model=InventoryItemRead)
async def patch_inventory_item(
    item_id: UUID,
    payload: InventoryItemUpdate,
    context: ManagementContextDep,
    session: SessionDep,
) -> InventoryItem:
    return await update_inventory_item(session, context, item_id, payload)


@router.get(
    "/inventory/movements",
    response_model=list[InventoryMovementRead],
)
async def get_inventory_movements(
    context: ManagementContextDep,
    session: SessionDep,
    item_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[InventoryMovement]:
    return await list_inventory_movements(
        session,
        context,
        item_id=item_id,
        limit=limit,
    )


@router.post(
    "/inventory/movements",
    response_model=InventoryMovementRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_inventory_movement(
    payload: InventoryMovementCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> InventoryMovement:
    return await create_inventory_movement(session, context, payload)


@router.get("/inventory/summary", response_model=InventorySummary)
async def get_inventory_summary(
    context: ManagementContextDep,
    session: SessionDep,
) -> InventorySummary:
    return InventorySummary.model_validate(
        await inventory_summary(session, context)
    )


@router.get("/material-requests", response_model=list[MaterialRequestRead])
async def get_material_requests(
    context: ReadContextDep,
    session: SessionDep,
    request_status: str | None = None,
    station_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[MaterialRequest]:
    return await list_material_requests(
        session,
        context,
        request_status=request_status,
        station_id=station_id,
        limit=limit,
    )


@router.post(
    "/material-requests",
    response_model=MaterialRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_material_request(
    payload: MaterialRequestCreate,
    context: FieldContextDep,
    session: SessionDep,
) -> MaterialRequest:
    return await create_material_request(session, context, payload)


@router.patch(
    "/material-requests/{request_id}",
    response_model=MaterialRequestRead,
)
async def patch_material_request(
    request_id: UUID,
    payload: MaterialRequestUpdate,
    context: ManagementContextDep,
    session: SessionDep,
) -> MaterialRequest:
    return await update_material_request(
        session,
        context,
        request_id,
        payload,
    )


@router.post(
    "/material-requests/{request_id}/issue",
    response_model=InventoryMovementRead,
)
async def post_material_request_issue(
    request_id: UUID,
    payload: MaterialRequestIssue,
    context: ManagementContextDep,
    session: SessionDep,
) -> InventoryMovement:
    return await issue_material_request(
        session,
        context,
        request_id,
        payload,
    )
