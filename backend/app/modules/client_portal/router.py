from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.client_portal.schemas import (
    ClientAccessCreate,
    ClientAccessRead,
    ClientPortalCredentialCreate,
    ClientPortalResponse,
)
from app.modules.client_portal.service import (
    build_client_portal,
    create_portal_credential,
    grant_client_access,
    list_client_access,
)

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
        ClientAccessRead.model_validate(item)
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


@router.post(
    "/clients/{client_id}/portal-credential",
    response_model=ClientAccessRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_portal_credential(
    client_id: UUID,
    payload: ClientPortalCredentialCreate,
    context: AdminContextDep,
    session: SessionDep,
) -> ClientAccessRead:
    return ClientAccessRead.model_validate(
        await create_portal_credential(
            session,
            context,
            client_id=client_id,
            email=str(payload.email),
            password=payload.password,
        )
    )
