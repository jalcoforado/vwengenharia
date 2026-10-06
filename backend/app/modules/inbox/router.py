from typing import Annotated

from fastapi import APIRouter, Depends

from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.inbox.schemas import InboxItem
from app.modules.inbox.service import build_inbox

router = APIRouter(tags=["fila"])

ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
    Role.TECNICO.value,
    Role.MANUTENCAO.value,
)
ContextDep = Annotated[AuthContext, Depends(require_roles(*ROLES))]


@router.get("/inbox", response_model=list[InboxItem])
async def get_inbox(
    context: ContextDep,
    session: SessionDep,
) -> list[InboxItem]:
    return [InboxItem.model_validate(item) for item in await build_inbox(session, context)]
