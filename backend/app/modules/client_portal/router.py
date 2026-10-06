from typing import Annotated

from fastapi import APIRouter, Depends

from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.client_portal.schemas import ClientAccessCreate, ClientAccessRead, ClientPortalResponse
from app.modules.client_portal.service import build_client_portal, grant_client_access, list_client_access

router = APIRouter(tags=["portal-cliente"])
ClientContextDep = Annotated[
    AuthContext,
    Depends(require_roles(Role.CLIENTE.value)),
]
AdminContextDep = Annotated[
    AuthContext,
    Depends(require_roles(Role.SUPERADMIN.value, Role.ADMIN.value)),
]


@router.get("/client-portal", response_model=ClientPortalResponse)
async def get_client_portal(
    context: ClientContextDep,
    session: SessionDep,
) -> ClientPortalResponse:
    return ClientPortalResponse.model_validate(
        await build_client_portal(session, context)
    )



@router.get("/client-access", response_model=list[ClientAccessRead])
async def get_client_access(
    context: AdminContextDep,
    session: SessionDep,
) -> list[ClientAccessRead]:
    return [
        ClientAccessRead.model_validate(item, from_attributes=True)
        for item in await list_client_access(session, context)
    ]


@router.post("/client-access", response_model=ClientAccessRead)
async def post_client_access(
    payload: ClientAccessCreate,
    context: AdminContextDep,
    session: SessionDep,
) -> ClientAccessRead:
    item = await grant_client_access(
        session,
        context,
        membership_id=payload.membership_id,
        client_id=payload.client_id,
    )
    return ClientAccessRead.model_validate(item, from_attributes=True)
