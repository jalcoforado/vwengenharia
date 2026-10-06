from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.identity import Role
from app.models.materials import MaterialRequest
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.materials.schemas import (
    MaterialRequestCreate,
    MaterialRequestRead,
    MaterialRequestUpdate,
)
from app.modules.materials.service import (
    create_material_request,
    list_material_requests,
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
