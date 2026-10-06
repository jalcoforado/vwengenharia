import asyncio
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.field import (
    Attachment,
    ChecklistTemplate,
    ChecklistTemplateItem,
    Measurement,
    SyncOperation,
    Visit,
    VisitAnswer,
    VisitPlan,
    VisitStatus,
)
from app.models.identity import Membership, Role
from app.models.operations import Asset, AssetStatus, AssetType, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit, tenant_get_or_404
from app.modules.field.schemas import (
    AttachmentRegisterCreate,
    ChecklistItemCreate,
    ChecklistTemplateCreate,
    MeasurementCreate,
    VisitAnswerUpsert,
    VisitCreate,
    VisitPlanCreate,
    VisitPlanUpdate,
)
from app.services.storage import get_storage

MANAGEMENT_ROLES = {
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
}
SELF_FIELD_ROLES = {Role.TECNICO.value, Role.MANUTENCAO.value}


async def get_tenant_membership(
    session: AsyncSession,
    tenant_id: UUID,
    membership_id: UUID,
) -> Membership:
    membership = (
        await session.execute(
            select(Membership).where(
                Membership.id == membership_id,
                Membership.tenant_id == tenant_id,
                Membership.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="membership_not_found")
    return membership


async def get_accessible_visit(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
) -> Visit:
    stmt = select(Visit).where(
        Visit.id == visit_id,
        Visit.tenant_id == context.tenant.id,
    )
    if context.membership.role in SELF_FIELD_ROLES:
        stmt = stmt.where(Visit.technician_membership_id == context.membership.id)
    visit = (await session.execute(stmt)).scalar_one_or_none()
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="visit_not_found")
    return visit


async def create_template(
    session: AsyncSession,
    context: AuthContext,
    payload: ChecklistTemplateCreate,
) -> ChecklistTemplate:
    template = ChecklistTemplate(tenant_id=context.tenant.id, **payload.model_dump())
    session.add(template)
    await session.flush()
    add_audit(
        session,
        context,
        action="CHECKLIST_TEMPLATE_CREATE",
        entity_type="checklist_template",
        entity_id=template.id,
    )
    await session.commit()
    await session.refresh(template)
    return template


async def add_template_item(
    session: AsyncSession,
    context: AuthContext,
    template_id: UUID,
    payload: ChecklistItemCreate,
) -> ChecklistTemplateItem:
    await tenant_get_or_404(
        session, ChecklistTemplate, context.tenant.id, template_id
    )
    if payload.asset_type_id is not None:
        await tenant_get_or_404(
            session, AssetType, context.tenant.id, payload.asset_type_id
        )
    item = ChecklistTemplateItem(
        tenant_id=context.tenant.id,
        template_id=template_id,
        **payload.model_dump(),
    )
    item.answer_type = payload.answer_type.value
    session.add(item)
    await session.flush()
    add_audit(
        session,
        context,
        action="CHECKLIST_ITEM_CREATE",
        entity_type="checklist_item",
        entity_id=item.id,
    )
    await session.commit()
    await session.refresh(item)
    return item


async def list_templates(
    session: AsyncSession,
    context: AuthContext,
) -> list[ChecklistTemplate]:
    stmt = (
        select(ChecklistTemplate)
        .where(
            ChecklistTemplate.tenant_id == context.tenant.id,
            ChecklistTemplate.is_active.is_(True),
        )
        .order_by(ChecklistTemplate.name, ChecklistTemplate.version.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_template_items(
    session: AsyncSession,
    context: AuthContext,
    template_id: UUID,
) -> list[ChecklistTemplateItem]:
    await tenant_get_or_404(
        session, ChecklistTemplate, context.tenant.id, template_id
    )
    stmt = (
        select(ChecklistTemplateItem)
        .where(
            ChecklistTemplateItem.tenant_id == context.tenant.id,
            ChecklistTemplateItem.template_id == template_id,
        )
        .order_by(ChecklistTemplateItem.position, ChecklistTemplateItem.code)
    )
    return list((await session.execute(stmt)).scalars().all())




async def create_visit_plan(
    session: AsyncSession,
    context: AuthContext,
    payload: VisitPlanCreate,
) -> VisitPlan:
    await tenant_get_or_404(session, Station, context.tenant.id, payload.station_id)
    technician = await get_tenant_membership(
        session, context.tenant.id, payload.technician_membership_id
    )
    if technician.role not in SELF_FIELD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="membership_is_not_field_role",
        )
    if payload.checklist_template_id is not None:
        await tenant_get_or_404(
            session,
            ChecklistTemplate,
            context.tenant.id,
            payload.checklist_template_id,
        )

    plan = VisitPlan(
        tenant_id=context.tenant.id,
        station_id=payload.station_id,
        technician_membership_id=payload.technician_membership_id,
        checklist_template_id=payload.checklist_template_id,
        frequency_days=payload.frequency_days,
        start_at=payload.start_at,
        end_at=payload.end_at,
        next_due_at=payload.start_at,
        notes=payload.notes,
        is_active=True,
    )
    session.add(plan)
    await session.flush()
    add_audit(
        session,
        context,
        action="VISIT_PLAN_CREATE",
        entity_type="visit_plan",
        entity_id=plan.id,
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def list_visit_plans(
    session: AsyncSession,
    context: AuthContext,
    *,
    active_only: bool = True,
    station_id: UUID | None = None,
) -> list[VisitPlan]:
    stmt = select(VisitPlan).where(VisitPlan.tenant_id == context.tenant.id)
    if active_only:
        stmt = stmt.where(VisitPlan.is_active.is_(True))
    if station_id is not None:
        stmt = stmt.where(VisitPlan.station_id == station_id)
    stmt = stmt.order_by(VisitPlan.next_due_at, VisitPlan.created_at)
    return list((await session.execute(stmt)).scalars().all())


async def update_visit_plan(
    session: AsyncSession,
    context: AuthContext,
    plan_id: UUID,
    payload: VisitPlanUpdate,
) -> VisitPlan:
    plan = await tenant_get_or_404(session, VisitPlan, context.tenant.id, plan_id)
    changes = payload.model_dump(exclude_unset=True)

    if "technician_membership_id" in changes:
        technician = await get_tenant_membership(
            session, context.tenant.id, changes["technician_membership_id"]
        )
        if technician.role not in SELF_FIELD_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="membership_is_not_field_role",
            )
    if changes.get("checklist_template_id") is not None:
        await tenant_get_or_404(
            session,
            ChecklistTemplate,
            context.tenant.id,
            changes["checklist_template_id"],
        )
    if "end_at" in changes and changes["end_at"] is not None:
        if changes["end_at"] < plan.start_at:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_at_before_start_at",
            )

    for field, value in changes.items():
        setattr(plan, field, value)

    add_audit(
        session,
        context,
        action="VISIT_PLAN_UPDATE",
        entity_type="visit_plan",
        entity_id=plan.id,
        fields=sorted(changes.keys()),
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def generate_visits_from_plans(
    session: AsyncSession,
    context: AuthContext,
    *,
    horizon_days: int,
) -> dict:
    now = datetime.now(UTC)
    horizon_until = now + timedelta(days=horizon_days)
    plans = list(
        (
            await session.execute(
                select(VisitPlan).where(
                    VisitPlan.tenant_id == context.tenant.id,
                    VisitPlan.is_active.is_(True),
                    VisitPlan.next_due_at <= horizon_until,
                )
            )
        ).scalars()
    )

    generated = 0
    already_existing = 0

    for plan in plans:
        due_at = plan.next_due_at
        while due_at <= horizon_until:
            if plan.end_at is not None and due_at > plan.end_at:
                plan.is_active = False
                break

            existing = (
                await session.execute(
                    select(Visit.id).where(
                        Visit.tenant_id == context.tenant.id,
                        Visit.visit_plan_id == plan.id,
                        Visit.scheduled_for == due_at,
                    )
                )
            ).scalar_one_or_none()

            if existing is None:
                session.add(
                    Visit(
                        tenant_id=context.tenant.id,
                        visit_plan_id=plan.id,
                        station_id=plan.station_id,
                        technician_membership_id=plan.technician_membership_id,
                        checklist_template_id=plan.checklist_template_id,
                        scheduled_for=due_at,
                        status=VisitStatus.PROGRAMADA.value,
                        notes=plan.notes,
                    )
                )
                generated += 1
            else:
                already_existing += 1

            due_at = due_at + timedelta(days=plan.frequency_days)

        plan.next_due_at = due_at
        if plan.end_at is not None and plan.next_due_at > plan.end_at:
            plan.is_active = False

    if plans:
        add_audit(
            session,
            context,
            action="VISIT_PLAN_GENERATE",
            entity_type="visit_plan",
            entity_id=None,
            fields=["generated", "horizon_until"],
        )
    await session.commit()

    return {
        "generated": generated,
        "already_existing": already_existing,
        "plans_processed": len(plans),
        "horizon_until": horizon_until,
    }


async def create_visit(
    session: AsyncSession,
    context: AuthContext,
    payload: VisitCreate,
) -> Visit:
    if payload.client_operation_id is not None:
        existing = (
            await session.execute(
                select(Visit).where(
                    Visit.tenant_id == context.tenant.id,
                    Visit.client_operation_id == payload.client_operation_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    await tenant_get_or_404(session, Station, context.tenant.id, payload.station_id)
    technician = await get_tenant_membership(
        session, context.tenant.id, payload.technician_membership_id
    )
    if technician.role not in SELF_FIELD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="membership_is_not_field_role",
        )
    if payload.checklist_template_id is not None:
        await tenant_get_or_404(
            session,
            ChecklistTemplate,
            context.tenant.id,
            payload.checklist_template_id,
        )

    visit = Visit(
        tenant_id=context.tenant.id,
        **payload.model_dump(),
        status=VisitStatus.PROGRAMADA.value,
    )
    session.add(visit)
    await session.flush()
    add_audit(
        session,
        context,
        action="VISIT_CREATE",
        entity_type="visit",
        entity_id=visit.id,
    )
    await session.commit()
    await session.refresh(visit)
    return visit


async def list_visits(
    session: AsyncSession,
    context: AuthContext,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    station_id: UUID | None = None,
    assigned_to_me: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Visit]:
    stmt = select(Visit).where(Visit.tenant_id == context.tenant.id)
    if context.membership.role in SELF_FIELD_ROLES or assigned_to_me:
        stmt = stmt.where(Visit.technician_membership_id == context.membership.id)
    if date_from is not None:
        stmt = stmt.where(Visit.scheduled_for >= date_from)
    if date_to is not None:
        stmt = stmt.where(Visit.scheduled_for <= date_to)
    if station_id is not None:
        stmt = stmt.where(Visit.station_id == station_id)
    stmt = stmt.order_by(Visit.scheduled_for).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def _find_sync_operation(
    session: AsyncSession,
    tenant_id: UUID,
    client_operation_id: UUID,
) -> SyncOperation | None:
    return (
        await session.execute(
            select(SyncOperation).where(
                SyncOperation.tenant_id == tenant_id,
                SyncOperation.client_operation_id == client_operation_id,
            )
        )
    ).scalar_one_or_none()


def _record_sync_operation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    client_operation_id: UUID,
    operation_type: str,
    entity_type: str,
    entity_id: UUID,
) -> None:
    session.add(
        SyncOperation(
            tenant_id=tenant_id,
            client_operation_id=client_operation_id,
            operation_type=operation_type,
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=datetime.now(UTC),
        )
    )


async def transition_visit(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    client_operation_id: UUID,
    *,
    operation: str,
) -> Visit:
    existing = await _find_sync_operation(
        session, context.tenant.id, client_operation_id
    )
    if existing is not None:
        if existing.entity_id != visit_id or existing.operation_type != operation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="client_operation_id_conflict",
            )
        return await get_accessible_visit(session, context, visit_id)

    visit = await get_accessible_visit(session, context, visit_id)
    now = datetime.now(UTC)

    if operation == "VISIT_START":
        if visit.status not in {
            VisitStatus.PROGRAMADA.value,
            VisitStatus.DEVOLVIDA.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="visit_not_startable",
            )
        visit.status = VisitStatus.EM_EXECUCAO.value
        visit.started_at = now
        visit.finished_at = None
    elif operation == "VISIT_FINISH":
        if visit.status != VisitStatus.EM_EXECUCAO.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="visit_not_in_progress",
            )
        await validate_required_answers(session, context, visit)
        visit.status = VisitStatus.AGUARDANDO_REVISAO.value
        visit.finished_at = now
    else:
        raise ValueError("unsupported operation")

    _record_sync_operation(
        session,
        tenant_id=context.tenant.id,
        client_operation_id=client_operation_id,
        operation_type=operation,
        entity_type="visit",
        entity_id=visit.id,
    )
    add_audit(
        session,
        context,
        action=operation,
        entity_type="visit",
        entity_id=visit.id,
    )
    await session.commit()
    await session.refresh(visit)
    return visit


async def validate_required_answers(
    session: AsyncSession,
    context: AuthContext,
    visit: Visit,
) -> None:
    if visit.checklist_template_id is None:
        return
    required_items = list(
        (
            await session.execute(
                select(ChecklistTemplateItem).where(
                    ChecklistTemplateItem.tenant_id == context.tenant.id,
                    ChecklistTemplateItem.template_id == visit.checklist_template_id,
                    ChecklistTemplateItem.required.is_(True),
                )
            )
        ).scalars()
    )
    if not required_items:
        return
    answered_ids = set(
        (
            await session.execute(
                select(VisitAnswer.item_id).where(
                    VisitAnswer.tenant_id == context.tenant.id,
                    VisitAnswer.visit_id == visit.id,
                )
            )
        ).scalars()
    )
    missing = [item.code for item in required_items if item.id not in answered_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "required_answers_missing", "items": missing},
        )


def _validated_answer_value(item: ChecklistTemplateItem, value):
    if value is None:
        if item.required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="required_answer_cannot_be_empty",
            )
        return value

    if item.answer_type == "BOOLEAN":
        if not isinstance(value, bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="answer_must_be_boolean",
            )
        return value

    if item.answer_type == "NUMBER":
        if isinstance(value, bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="answer_must_be_number",
            )
        try:
            numeric = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="answer_must_be_number",
            ) from None
        return float(numeric)

    if item.answer_type in {"SELECT", "ASSET_STATUS"}:
        if not isinstance(value, str) or not value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="answer_must_be_option",
            )
        allowed = item.options_json
        if item.answer_type == "ASSET_STATUS" and not allowed:
            allowed = [state.value for state in AssetStatus]
        if allowed and value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="answer_option_not_allowed",
            )
        return value

    if item.answer_type == "TEXT":
        if not isinstance(value, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="answer_must_be_text",
            )
        if item.required and not value.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="required_answer_cannot_be_empty",
            )
        return value

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="unsupported_answer_type",
    )


async def _sync_replay_entity(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    client_operation_id: UUID | None,
    operation_type: str,
    entity_type: str,
    model,
):
    if client_operation_id is None:
        return None
    operation = await _find_sync_operation(session, tenant_id, client_operation_id)
    if operation is None:
        return None
    if operation.operation_type != operation_type or operation.entity_type != entity_type:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="client_operation_id_conflict",
        )
    entity = (
        await session.execute(
            select(model).where(
                model.id == operation.entity_id,
                model.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotent_entity_missing",
        )
    return entity


async def upsert_answer(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload: VisitAnswerUpsert,
) -> VisitAnswer:
    visit = await get_accessible_visit(session, context, visit_id)

    replay = await _sync_replay_entity(
        session,
        tenant_id=context.tenant.id,
        client_operation_id=payload.client_operation_id,
        operation_type="VISIT_ANSWER_UPSERT",
        entity_type="visit_answer",
        model=VisitAnswer,
    )
    if replay is not None:
        if replay.visit_id != visit.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="client_operation_id_conflict",
            )
        return replay

    if visit.status != VisitStatus.EM_EXECUCAO.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_not_in_progress")
    if visit.checklist_template_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="visit_has_no_template")

    item = (
        await session.execute(
            select(ChecklistTemplateItem).where(
                ChecklistTemplateItem.id == payload.item_id,
                ChecklistTemplateItem.tenant_id == context.tenant.id,
                ChecklistTemplateItem.template_id == visit.checklist_template_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_item_not_found")

    normalized_value = _validated_answer_value(item, payload.value)

    answer = (
        await session.execute(
            select(VisitAnswer).where(
                VisitAnswer.tenant_id == context.tenant.id,
                VisitAnswer.visit_id == visit.id,
                VisitAnswer.item_id == item.id,
            )
        )
    ).scalar_one_or_none()
    if answer is None:
        answer = VisitAnswer(
            tenant_id=context.tenant.id,
            visit_id=visit.id,
            item_id=item.id,
            value_json=normalized_value,
            client_operation_id=payload.client_operation_id,
        )
        session.add(answer)
    else:
        answer.value_json = normalized_value

    await session.flush()
    if payload.client_operation_id is not None:
        _record_sync_operation(
            session,
            tenant_id=context.tenant.id,
            client_operation_id=payload.client_operation_id,
            operation_type="VISIT_ANSWER_UPSERT",
            entity_type="visit_answer",
            entity_id=answer.id,
        )
    add_audit(
        session,
        context,
        action="VISIT_ANSWER_UPSERT",
        entity_type="visit_answer",
        entity_id=answer.id,
    )
    await session.commit()
    await session.refresh(answer)
    return answer


async def add_measurement(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload: MeasurementCreate,
) -> Measurement:
    visit = await get_accessible_visit(session, context, visit_id)

    replay = await _sync_replay_entity(
        session,
        tenant_id=context.tenant.id,
        client_operation_id=payload.client_operation_id,
        operation_type="MEASUREMENT_CREATE",
        entity_type="measurement",
        model=Measurement,
    )
    if replay is not None:
        if replay.visit_id != visit.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="client_operation_id_conflict",
            )
        return replay

    if visit.status != VisitStatus.EM_EXECUCAO.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_not_in_progress")

    data = payload.model_dump()
    data["status"] = payload.status.value
    measurement = Measurement(
        tenant_id=context.tenant.id,
        visit_id=visit.id,
        **data,
    )
    session.add(measurement)
    await session.flush()
    if payload.client_operation_id is not None:
        _record_sync_operation(
            session,
            tenant_id=context.tenant.id,
            client_operation_id=payload.client_operation_id,
            operation_type="MEASUREMENT_CREATE",
            entity_type="measurement",
            entity_id=measurement.id,
        )
    add_audit(
        session,
        context,
        action="MEASUREMENT_CREATE",
        entity_type="measurement",
        entity_id=measurement.id,
    )
    await session.commit()
    await session.refresh(measurement)
    return measurement


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return cleaned[:120] or "arquivo"


async def register_attachment(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload: AttachmentRegisterCreate,
) -> Attachment:
    visit = await get_accessible_visit(session, context, visit_id)

    replay = await _sync_replay_entity(
        session,
        tenant_id=context.tenant.id,
        client_operation_id=payload.client_operation_id,
        operation_type="ATTACHMENT_REGISTER",
        entity_type="attachment",
        model=Attachment,
    )
    if replay is not None:
        if replay.visit_id != visit.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="client_operation_id_conflict",
            )
        return replay

    if payload.asset_id is not None:
        asset = await tenant_get_or_404(
            session, Asset, context.tenant.id, payload.asset_id
        )
        if asset.station_id != visit.station_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="asset_not_in_visit_station",
            )

    attachment_id = uuid4()
    object_key = (
        f"{context.tenant.id}/visits/{visit.id}/{attachment_id}-"
        f"{_safe_filename(payload.filename)}"
    )
    attachment = Attachment(
        id=attachment_id,
        tenant_id=context.tenant.id,
        visit_id=visit.id,
        asset_id=payload.asset_id,
        object_key=object_key,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        caption=payload.caption,
        client_operation_id=payload.client_operation_id,
    )
    session.add(attachment)
    await session.flush()
    if payload.client_operation_id is not None:
        _record_sync_operation(
            session,
            tenant_id=context.tenant.id,
            client_operation_id=payload.client_operation_id,
            operation_type="ATTACHMENT_REGISTER",
            entity_type="attachment",
            entity_id=attachment.id,
        )
    add_audit(
        session,
        context,
        action="ATTACHMENT_REGISTER",
        entity_type="attachment",
        entity_id=attachment.id,
    )
    await session.commit()
    await session.refresh(attachment)
    return attachment


async def build_field_bootstrap(
    session: AsyncSession,
    context: AuthContext,
) -> dict:
    now = datetime.now(UTC)
    visits = await list_visits(
        session,
        context,
        date_from=now - timedelta(days=7),
        date_to=now + timedelta(days=30),
        assigned_to_me=True,
        limit=500,
    )
    station_ids = {visit.station_id for visit in visits}
    template_ids = {
        visit.checklist_template_id
        for visit in visits
        if visit.checklist_template_id is not None
    }

    stations = []
    assets = []
    templates = []
    items = []
    answers = []
    measurements = []
    attachments = []

    visit_ids = {visit.id for visit in visits}
    if visit_ids:
        answers = list(
            (
                await session.execute(
                    select(VisitAnswer).where(
                        VisitAnswer.tenant_id == context.tenant.id,
                        VisitAnswer.visit_id.in_(visit_ids),
                    )
                )
            ).scalars()
        )
        measurements = list(
            (
                await session.execute(
                    select(Measurement).where(
                        Measurement.tenant_id == context.tenant.id,
                        Measurement.visit_id.in_(visit_ids),
                    )
                )
            ).scalars()
        )
        attachments = list(
            (
                await session.execute(
                    select(Attachment).where(
                        Attachment.tenant_id == context.tenant.id,
                        Attachment.visit_id.in_(visit_ids),
                    )
                )
            ).scalars()
        )

    if station_ids:
        stations = list(
            (
                await session.execute(
                    select(Station).where(
                        Station.tenant_id == context.tenant.id,
                        Station.id.in_(station_ids),
                    )
                )
            ).scalars()
        )
        assets = list(
            (
                await session.execute(
                    select(Asset).where(
                        Asset.tenant_id == context.tenant.id,
                        Asset.station_id.in_(station_ids),
                        Asset.is_active.is_(True),
                    )
                )
            ).scalars()
        )
    if template_ids:
        templates = list(
            (
                await session.execute(
                    select(ChecklistTemplate).where(
                        ChecklistTemplate.tenant_id == context.tenant.id,
                        ChecklistTemplate.id.in_(template_ids),
                    )
                )
            ).scalars()
        )
        items = list(
            (
                await session.execute(
                    select(ChecklistTemplateItem)
                    .where(
                        ChecklistTemplateItem.tenant_id == context.tenant.id,
                        ChecklistTemplateItem.template_id.in_(template_ids),
                    )
                    .order_by(
                        ChecklistTemplateItem.template_id,
                        ChecklistTemplateItem.position,
                    )
                )
            ).scalars()
        )

    return {
        "generated_at": now,
        "visits": visits,
        "stations": stations,
        "assets": assets,
        "templates": templates,
        "items": items,
        "answers": answers,
        "measurements": measurements,
        "attachments": attachments,
    }


ALLOWED_EVIDENCE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/quicktime",
    "application/pdf",
}


async def presign_attachment_upload(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload: AttachmentRegisterCreate,
) -> dict:
    if payload.content_type not in ALLOWED_EVIDENCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="unsupported_attachment_type",
        )
    attachment = await register_attachment(session, context, visit_id, payload)
    upload_url = get_storage().presign_put(
        object_key=attachment.object_key,
        content_type=attachment.content_type,
    )
    return {
        "attachment": attachment,
        "upload_url": upload_url,
        "expires_in": settings.s3_presign_seconds,
        "required_headers": {"Content-Type": attachment.content_type},
    }


async def complete_attachment_upload(
    session: AsyncSession,
    context: AuthContext,
    attachment_id: UUID,
) -> Attachment:
    attachment = await tenant_get_or_404(
        session,
        Attachment,
        context.tenant.id,
        attachment_id,
    )
    await get_accessible_visit(session, context, attachment.visit_id)

    metadata = await asyncio.to_thread(
        get_storage().object_metadata,
        object_key=attachment.object_key,
    )
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="attachment_not_uploaded",
        )

    actual_size = int(metadata.get("ContentLength", 0))
    if attachment.size_bytes is not None and actual_size != attachment.size_bytes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="attachment_size_mismatch",
        )

    stored_type = metadata.get("ContentType")
    if stored_type and stored_type != attachment.content_type:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="attachment_content_type_mismatch",
        )

    attachment.storage_status = "UPLOADED"
    attachment.uploaded_at = datetime.now(UTC)
    add_audit(
        session,
        context,
        action="ATTACHMENT_UPLOAD_COMPLETE",
        entity_type="attachment",
        entity_id=attachment.id,
        fields=["storage_status", "uploaded_at"],
    )
    await session.commit()
    await session.refresh(attachment)
    return attachment
