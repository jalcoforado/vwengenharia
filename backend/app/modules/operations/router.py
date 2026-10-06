from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.identity import Role
from app.models.maintenance import Occurrence, WorkOrder, WorkOrderStatusHistory
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.operations.schemas import (
    DashboardOverview,
    DashboardSla,
    OccurrenceCreate,
    OccurrenceRead,
    VisitReviewCreate,
    VisitReviewRead,
    WorkOrderAssign,
    WorkOrderCreate,
    WorkOrderHistoryRead,
    WorkOrderRead,
    WorkOrderTransition,
)
from app.modules.operations.service import (
    assign_work_order,
    create_occurrence,
    create_work_order,
    dashboard_overview,
    dashboard_sla,
    list_occurrences,
    list_work_orders,
    review_visit,
    transition_work_order,
    work_order_history,
)

router = APIRouter(tags=["operacoes"])

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
FIELD_ROLES = INTERNAL_ROLES

ReadContextDep = Annotated[AuthContext, Depends(require_roles(*INTERNAL_ROLES))]
ManagementContextDep = Annotated[AuthContext, Depends(require_roles(*MANAGEMENT_ROLES))]
FieldContextDep = Annotated[AuthContext, Depends(require_roles(*FIELD_ROLES))]
PageLimit = Annotated[int, Query(ge=1, le=500)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("/occurrences", response_model=list[OccurrenceRead])
async def get_occurrences(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    occurrence_status: str | None = None,
    severity: str | None = None,
    station_id: UUID | None = None,
) -> list[Occurrence]:
    return await list_occurrences(
        session,
        context,
        occurrence_status=occurrence_status,
        severity=severity,
        station_id=station_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/occurrences",
    response_model=OccurrenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_occurrence(
    payload: OccurrenceCreate,
    context: FieldContextDep,
    session: SessionDep,
) -> Occurrence:
    return await create_occurrence(session, context, payload)


@router.get("/work-orders", response_model=list[WorkOrderRead])
async def get_work_orders(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    work_order_status: str | None = None,
    priority: str | None = None,
    overdue_only: bool = False,
) -> list[WorkOrder]:
    return await list_work_orders(
        session,
        context,
        work_order_status=work_order_status,
        priority=priority,
        overdue_only=overdue_only,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/work-orders",
    response_model=WorkOrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_work_order(
    payload: WorkOrderCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> WorkOrder:
    return await create_work_order(session, context, payload)


@router.post("/work-orders/{work_order_id}/assign", response_model=WorkOrderRead)
async def post_work_order_assignment(
    work_order_id: UUID,
    payload: WorkOrderAssign,
    context: ManagementContextDep,
    session: SessionDep,
) -> WorkOrder:
    return await assign_work_order(session, context, work_order_id, payload)


@router.post("/work-orders/{work_order_id}/transition", response_model=WorkOrderRead)
async def post_work_order_transition(
    work_order_id: UUID,
    payload: WorkOrderTransition,
    context: FieldContextDep,
    session: SessionDep,
) -> WorkOrder:
    return await transition_work_order(session, context, work_order_id, payload)


@router.get(
    "/work-orders/{work_order_id}/history",
    response_model=list[WorkOrderHistoryRead],
)
async def get_work_order_history(
    work_order_id: UUID,
    context: ReadContextDep,
    session: SessionDep,
) -> list[WorkOrderStatusHistory]:
    return await work_order_history(session, context, work_order_id)


@router.post("/visits/{visit_id}/review", response_model=VisitReviewRead)
async def post_visit_review(
    visit_id: UUID,
    payload: VisitReviewCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> VisitReviewRead:
    return await review_visit(session, context, visit_id, payload)


@router.get("/dashboard/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    context: ManagementContextDep,
    session: SessionDep,
) -> DashboardOverview:
    return DashboardOverview.model_validate(await dashboard_overview(session, context))


@router.get("/dashboard/sla", response_model=DashboardSla)
async def get_dashboard_sla(
    context: ManagementContextDep,
    session: SessionDep,
) -> DashboardSla:
    return DashboardSla(buckets=await dashboard_sla(session, context))
