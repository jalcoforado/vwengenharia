import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import (
    Attachment,
    ChecklistTemplate,
    ChecklistTemplateItem,
    Measurement,
    MeasurementStatus,
    SyncOperation,
    Visit,
    VisitAnswer,
    VisitStatus,
)
from app.models.identity import Membership, Role
from app.models.operations import Asset, AssetType, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit, tenant_get_or_404
from app.modules.field.schemas import (
    AttachmentRegisterCreate,
    ChecklistItemCreate,
    ChecklistTemplateCreate,
    MeasurementCreate,
    VisitAnswerUpsert,
    VisitCreate,
)

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
        if visit.status != VisitStatus.PROGRAMADA.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="visit_not_programmed",
            )
        visit.status = VisitStatus.EM_EXECUCAO.value
        visit.started_at = now
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


async def upsert_answer(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload: VisitAnswerUpsert,
) -> VisitAnswer:
    visit = await get_accessible_visit(session, context, visit_id)
    if visit.status != VisitStatus.EM_EXECUCAO.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_not_in_progress")
    if visit.checklist_template_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="visit_has_no_template")

    if payload.client_operation_id is not None:
        existing_by_operation = (
            await session.execute(
                select(VisitAnswer).where(
                    VisitAnswer.tenant_id == context.tenant.id,
                    VisitAnswer.client_operation_id == payload.client_operation_id,
                )
            )
        ).scalar_one_or_none()
        if existing_by_operation is not None:
            return existing_by_operation

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
            value_json=payload.value,
            client_operation_id=payload.client_operation_id,
        )
        session.add(answer)
    else:
        answer.value_json = payload.value
        if payload.client_operation_id is not None:
            answer.client_operation_id = payload.client_operation_id

    await session.flush()
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
    if visit.status != VisitStatus.EM_EXECUCAO.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_not_in_progress")

    if payload.client_operation_id is not None:
        existing = (
            await session.execute(
                select(Measurement).where(
                    Measurement.tenant_id == context.tenant.id,
                    Measurement.client_operation_id == payload.client_operation_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    data = payload.model_dump()
    data["status"] = payload.status.value
    measurement = Measurement(
        tenant_id=context.tenant.id,
        visit_id=visit.id,
        **data,
    )
    session.add(measurement)
    await session.flush()
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

    if payload.client_operation_id is not None:
        existing = (
            await session.execute(
                select(Attachment).where(
                    Attachment.tenant_id == context.tenant.id,
                    Attachment.client_operation_id == payload.client_operation_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

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
