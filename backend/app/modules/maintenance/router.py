from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.identity import Role
from app.models.maintenance import MaintenanceExecution, MaintenancePlan
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.maintenance.schemas import (
    MaintenanceExecutionCreate,
    MaintenanceExecutionRead,
    MaintenancePlanCreate,
    MaintenancePlanRead,
    MaintenancePlanUpdate,
    MaintenanceSummary,
)
from app.modules.maintenance.service import (
    create_execution,
    create_plan,
    list_executions,
    list_plans,
    maintenance_summary,
    update_plan,
)

router = APIRouter(tags=["manutencao"])

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


@router.get("/maintenance/plans", response_model=list[MaintenancePlanRead])
async def get_maintenance_plans(
    context: ReadContextDep,
    session: SessionDep,
    overdue_only: bool = False,
    active_only: bool = True,
    asset_id: UUID | None = None,
) -> list[MaintenancePlan]:
    return await list_plans(
        session,
        context,
        overdue_only=overdue_only,
        active_only=active_only,
        asset_id=asset_id,
    )


@router.post(
    "/maintenance/plans",
    response_model=MaintenancePlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_maintenance_plan(
    payload: MaintenancePlanCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> MaintenancePlan:
    return await create_plan(session, context, payload)


@router.patch("/maintenance/plans/{plan_id}", response_model=MaintenancePlanRead)
async def patch_maintenance_plan(
    plan_id: UUID,
    payload: MaintenancePlanUpdate,
    context: ManagementContextDep,
    session: SessionDep,
) -> MaintenancePlan:
    return await update_plan(session, context, plan_id, payload)


@router.get(
    "/maintenance/executions",
    response_model=list[MaintenanceExecutionRead],
)
async def get_maintenance_executions(
    context: ReadContextDep,
    session: SessionDep,
    asset_id: UUID | None = None,
    plan_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[MaintenanceExecution]:
    return await list_executions(
        session,
        context,
        asset_id=asset_id,
        plan_id=plan_id,
        limit=limit,
    )


@router.post(
    "/maintenance/executions",
    response_model=MaintenanceExecutionRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_maintenance_execution(
    payload: MaintenanceExecutionCreate,
    context: FieldContextDep,
    session: SessionDep,
) -> MaintenanceExecution:
    return await create_execution(session, context, payload)


@router.get("/maintenance/summary", response_model=MaintenanceSummary)
async def get_maintenance_summary(
    context: ManagementContextDep,
    session: SessionDep,
) -> MaintenanceSummary:
    return MaintenanceSummary.model_validate(
        await maintenance_summary(session, context)
    )
