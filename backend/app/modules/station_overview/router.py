from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.station_overview.schemas import StationOverviewResponse
from app.modules.station_overview.service import station_overview

router = APIRouter(tags=["estacoes"])

READ_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
    Role.TECNICO.value,
    Role.MANUTENCAO.value,
)
ReadContextDep = Annotated[AuthContext, Depends(require_roles(*READ_ROLES))]


@router.get(
    "/stations/{station_id}/overview",
    response_model=StationOverviewResponse,
)
async def get_station_overview(
    station_id: UUID,
    context: ReadContextDep,
    session: SessionDep,
) -> StationOverviewResponse:
    return StationOverviewResponse.model_validate(
        await station_overview(session, context, station_id)
    )
