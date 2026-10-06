from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.models.ai import AiRun
from app.models.identity import Role
from app.modules.ai.schemas import AskRequest, AskResponse, ToolTraceItem
from app.modules.ai.service import ask_sonia, get_run
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles

router = APIRouter(prefix="/ai", tags=["ai"])

AI_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
)
AiContextDep = Annotated[AuthContext, Depends(require_roles(*AI_ROLES))]


def to_response(run: AiRun) -> AskResponse:
    return AskResponse(
        run_id=run.id,
        answer=run.answer or "",
        tool_trace=[ToolTraceItem.model_validate(item) for item in run.tool_trace],
        provider=run.provider,
        model=run.model,
    )


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    context: AiContextDep,
    session: SessionDep,
) -> AskResponse:
    run = await ask_sonia(session, context, payload.question.strip())
    return to_response(run)


@router.get("/runs/{run_id}", response_model=AskResponse)
async def read_run(
    run_id: UUID,
    context: AiContextDep,
    session: SessionDep,
) -> AskResponse:
    return to_response(await get_run(session, context, run_id))
