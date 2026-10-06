from typing import Annotated

from fastapi import APIRouter, Depends

from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.client_portal.schemas import ClientPortalResponse
from app.modules.client_portal.service import build_client_portal

router = APIRouter(tags=["portal-cliente"])
ClientContextDep = Annotated[
    AuthContext,
    Depends(require_roles(Role.CLIENTE.value)),
]


@router.get("/client-portal", response_model=ClientPortalResponse)
async def get_client_portal(
    context: ClientContextDep,
    session: SessionDep,
) -> ClientPortalResponse:
    return ClientPortalResponse.model_validate(
        await build_client_portal(session, context)
    )
