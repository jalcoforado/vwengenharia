from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.field import ChecklistTemplate, ChecklistTemplateItem, Visit
from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.field.schemas import (
    AssetSituationRead,
    AssetSituationUpsert,
    AttachmentPresignResponse,
    AttachmentRead,
    AttachmentRegisterCreate,
    ChecklistItemCreate,
    ChecklistItemRead,
    ChecklistTemplateCreate,
    ChecklistTemplateRead,
    FieldBootstrapResponse,
    MeasurementCreate,
    MeasurementRead,
    VisitAnswerRead,
    VisitAnswerUpsert,
    VisitCommand,
    VisitCreate,
    VisitGenerationRequest,
    VisitGenerationResponse,
    VisitPlanCreate,
    VisitPlanRead,
    VisitPlanUpdate,
    VisitRead,
)
from app.modules.field.service import (
    add_measurement,
    add_template_item,
    build_field_bootstrap,
    complete_attachment_upload,
    create_template,
    create_visit,
    create_visit_plan,
    generate_visits_from_plans,
    list_template_items,
    list_templates,
    list_visit_plans,
    list_visits,
    presign_attachment_upload,
    register_attachment,
    transition_visit,
    update_visit_plan,
    upsert_answer,
    upsert_asset_situation,
)

router = APIRouter(tags=["campo"])

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
FIELD_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
    Role.TECNICO.value,
    Role.MANUTENCAO.value,
)

ReadContextDep = Annotated[AuthContext, Depends(require_roles(*INTERNAL_ROLES))]
ManagementContextDep = Annotated[AuthContext, Depends(require_roles(*MANAGEMENT_ROLES))]
FieldContextDep = Annotated[AuthContext, Depends(require_roles(*FIELD_ROLES))]
PageLimit = Annotated[int, Query(ge=1, le=500)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("/checklist-templates", response_model=list[ChecklistTemplateRead])
async def get_templates(
    context: ReadContextDep,
    session: SessionDep,
) -> list[ChecklistTemplate]:
    return await list_templates(session, context)


@router.post(
    "/checklist-templates",
    response_model=ChecklistTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_template(
    payload: ChecklistTemplateCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> ChecklistTemplate:
    return await create_template(session, context, payload)


@router.get(
    "/checklist-templates/{template_id}/items",
    response_model=list[ChecklistItemRead],
)
async def get_template_items(
    template_id: UUID,
    context: ReadContextDep,
    session: SessionDep,
) -> list[ChecklistTemplateItem]:
    return await list_template_items(session, context, template_id)


@router.post(
    "/checklist-templates/{template_id}/items",
    response_model=ChecklistItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_template_item(
    template_id: UUID,
    payload: ChecklistItemCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> ChecklistTemplateItem:
    return await add_template_item(session, context, template_id, payload)




@router.get("/visit-plans", response_model=list[VisitPlanRead])
async def get_visit_plans(
    context: ManagementContextDep,
    session: SessionDep,
    active_only: bool = True,
    station_id: UUID | None = None,
) -> list:
    return await list_visit_plans(
        session,
        context,
        active_only=active_only,
        station_id=station_id,
    )


@router.post(
    "/visit-plans",
    response_model=VisitPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_visit_plan(
    payload: VisitPlanCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> VisitPlanRead:
    return await create_visit_plan(session, context, payload)


@router.patch("/visit-plans/{plan_id}", response_model=VisitPlanRead)
async def patch_visit_plan(
    plan_id: UUID,
    payload: VisitPlanUpdate,
    context: ManagementContextDep,
    session: SessionDep,
) -> VisitPlanRead:
    return await update_visit_plan(session, context, plan_id, payload)


@router.post("/visit-plans/generate", response_model=VisitGenerationResponse)
async def post_generate_visit_plans(
    payload: VisitGenerationRequest,
    context: ManagementContextDep,
    session: SessionDep,
) -> VisitGenerationResponse:
    data = await generate_visits_from_plans(
        session,
        context,
        horizon_days=payload.horizon_days,
    )
    return VisitGenerationResponse.model_validate(data)


@router.get("/visits", response_model=list[VisitRead])
async def get_visits(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    station_id: UUID | None = None,
    assigned_to_me: bool = False,
) -> list[Visit]:
    return await list_visits(
        session,
        context,
        date_from=date_from,
        date_to=date_to,
        station_id=station_id,
        assigned_to_me=assigned_to_me,
        limit=limit,
        offset=offset,
    )


@router.post("/visits", response_model=VisitRead, status_code=status.HTTP_201_CREATED)
async def post_visit(
    payload: VisitCreate,
    context: ManagementContextDep,
    session: SessionDep,
) -> Visit:
    return await create_visit(session, context, payload)


@router.post("/visits/{visit_id}/start", response_model=VisitRead)
async def start_visit(
    visit_id: UUID,
    payload: VisitCommand,
    context: FieldContextDep,
    session: SessionDep,
) -> Visit:
    return await transition_visit(
        session,
        context,
        visit_id,
        payload.client_operation_id,
        operation="VISIT_START",
    )


@router.post("/visits/{visit_id}/finish", response_model=VisitRead)
async def finish_visit(
    visit_id: UUID,
    payload: VisitCommand,
    context: FieldContextDep,
    session: SessionDep,
) -> Visit:
    return await transition_visit(
        session,
        context,
        visit_id,
        payload.client_operation_id,
        operation="VISIT_FINISH",
    )


@router.put("/visits/{visit_id}/answers", response_model=VisitAnswerRead)
async def put_visit_answer(
    visit_id: UUID,
    payload: VisitAnswerUpsert,
    context: FieldContextDep,
    session: SessionDep,
) -> VisitAnswerRead:
    return await upsert_answer(session, context, visit_id, payload)


@router.put("/visits/{visit_id}/asset-situations", response_model=AssetSituationRead)
async def put_asset_situation(
    visit_id: UUID,
    payload: AssetSituationUpsert,
    context: FieldContextDep,
    session: SessionDep,
) -> AssetSituationRead:
    return await upsert_asset_situation(session, context, visit_id, payload)


@router.post(
    "/visits/{visit_id}/measurements",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_measurement(
    visit_id: UUID,
    payload: MeasurementCreate,
    context: FieldContextDep,
    session: SessionDep,
) -> MeasurementRead:
    return await add_measurement(session, context, visit_id, payload)


@router.post(
    "/visits/{visit_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_attachment(
    visit_id: UUID,
    payload: AttachmentRegisterCreate,
    context: FieldContextDep,
    session: SessionDep,
) -> AttachmentRead:
    return await register_attachment(session, context, visit_id, payload)


@router.post(
    "/visits/{visit_id}/attachments/presign",
    response_model=AttachmentPresignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def presign_attachment(
    visit_id: UUID,
    payload: AttachmentRegisterCreate,
    context: FieldContextDep,
    session: SessionDep,
) -> AttachmentPresignResponse:
    data = await presign_attachment_upload(session, context, visit_id, payload)
    return AttachmentPresignResponse.model_validate(data)


@router.post(
    "/attachments/{attachment_id}/complete",
    response_model=AttachmentRead,
)
async def complete_attachment(
    attachment_id: UUID,
    context: FieldContextDep,
    session: SessionDep,
) -> AttachmentRead:
    return await complete_attachment_upload(session, context, attachment_id)


@router.get("/field/bootstrap", response_model=FieldBootstrapResponse)
async def field_bootstrap(
    context: FieldContextDep,
    session: SessionDep,
) -> FieldBootstrapResponse:
    data = await build_field_bootstrap(session, context)
    return FieldBootstrapResponse.model_validate(data)
