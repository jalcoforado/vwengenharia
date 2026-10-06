from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.field import ChecklistTemplate, Measurement, Visit
from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.field_visits.schemas import (
    ChecklistTemplateCreate,
    ChecklistTemplateDetail,
    ChecklistTemplateRead,
    MeasurementRead,
    MeasurementsRequest,
    SyncAck,
    VisitAnswersRequest,
    VisitCreate,
    VisitFinishRequest,
    VisitRead,
    VisitStartRequest,
)
from app.modules.field_visits.service import (
    create_template,
    create_visit,
    finish_visit,
    get_template_detail,
    get_visit_for_context,
    list_measurements,
    list_templates,
    list_visits,
    save_answers,
    save_measurements,
    start_visit,
)

router = APIRouter(tags=["campo"])

MANAGER_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
)
FIELD_ROLES = MANAGER_ROLES + (Role.TECNICO.value,)

ManagerContextDep = Annotated[AuthContext, Depends(require_roles(*MANAGER_ROLES))]
FieldContextDep = Annotated[AuthContext, Depends(require_roles(*FIELD_ROLES))]
PageLimit = Annotated[int, Query(ge=1, le=500)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("/checklist-templates", response_model=list[ChecklistTemplateRead])
async def get_templates(
    context: FieldContextDep,
    session: SessionDep,
    active_only: bool = True,
) -> list[ChecklistTemplate]:
    return await list_templates(session, context, active_only=active_only)


@router.post(
    "/checklist-templates",
    response_model=ChecklistTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_template(
    payload: ChecklistTemplateCreate,
    context: ManagerContextDep,
    session: SessionDep,
) -> ChecklistTemplate:
    return await create_template(session, context, payload)


@router.get(
    "/checklist-templates/{template_id}",
    response_model=ChecklistTemplateDetail,
)
async def get_template(
    template_id: UUID,
    context: FieldContextDep,
    session: SessionDep,
) -> ChecklistTemplateDetail:
    template, items = await get_template_detail(session, context, template_id)
    return ChecklistTemplateDetail(
        id=template.id,
        name=template.name,
        station_type=template.station_type,
        version=template.version,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
        items=items,
    )


@router.post("/visits", response_model=VisitRead, status_code=status.HTTP_201_CREATED)
async def post_visit(
    payload: VisitCreate,
    context: ManagerContextDep,
    session: SessionDep,
) -> Visit:
    return await create_visit(session, context, payload)


@router.get("/visits", response_model=list[VisitRead])
async def get_visits(
    context: FieldContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    visit_status: str | None = Query(default=None, alias="status"),
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
) -> list[Visit]:
    return await list_visits(
        session,
        context,
        visit_status=visit_status,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
        limit=limit,
        offset=offset,
    )


@router.get("/visits/{visit_id}", response_model=VisitRead)
async def get_visit(
    visit_id: UUID,
    context: FieldContextDep,
    session: SessionDep,
) -> Visit:
    return await get_visit_for_context(session, context, visit_id)


@router.post("/visits/{visit_id}/start", response_model=VisitRead)
async def post_start_visit(
    visit_id: UUID,
    payload: VisitStartRequest,
    context: FieldContextDep,
    session: SessionDep,
) -> Visit:
    return await start_visit(
        session,
        context,
        visit_id,
        payload.client_operation_id,
    )


@router.put("/visits/{visit_id}/answers", response_model=SyncAck)
async def put_visit_answers(
    visit_id: UUID,
    payload: VisitAnswersRequest,
    context: FieldContextDep,
    session: SessionDep,
) -> SyncAck:
    return await save_answers(session, context, visit_id, payload)


@router.post("/visits/{visit_id}/measurements", response_model=SyncAck)
async def post_measurements(
    visit_id: UUID,
    payload: MeasurementsRequest,
    context: FieldContextDep,
    session: SessionDep,
) -> SyncAck:
    return await save_measurements(session, context, visit_id, payload)


@router.get("/visits/{visit_id}/measurements", response_model=list[MeasurementRead])
async def get_measurements(
    visit_id: UUID,
    context: FieldContextDep,
    session: SessionDep,
) -> list[Measurement]:
    return await list_measurements(session, context, visit_id)


@router.post("/visits/{visit_id}/finish", response_model=VisitRead)
async def post_finish_visit(
    visit_id: UUID,
    payload: VisitFinishRequest,
    context: FieldContextDep,
    session: SessionDep,
) -> Visit:
    return await finish_visit(session, context, visit_id, payload)
