from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    Measurement,
    OperationReceipt,
    Visit,
    VisitAnswer,
    VisitStatus,
)
from app.models.identity import Membership, Role
from app.models.operations import Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit, tenant_get_or_404
from app.modules.field_visits.schemas import SyncAck

MANAGER_ROLES = {
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
}
FIELD_ROLES = MANAGER_ROLES | {Role.TECNICO.value}


async def get_receipt(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    client_operation_id: UUID,
    action: str,
) -> OperationReceipt | None:
    receipt = (
        await session.execute(
            select(OperationReceipt).where(
                OperationReceipt.tenant_id == tenant_id,
                OperationReceipt.client_operation_id == client_operation_id,
            )
        )
    ).scalar_one_or_none()
    if receipt is not None and receipt.action != action:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="client_operation_id_reused",
        )
    return receipt


def save_receipt(
    session: AsyncSession,
    context: AuthContext,
    *,
    client_operation_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    response_payload: dict | None = None,
) -> None:
    session.add(
        OperationReceipt(
            tenant_id=context.tenant.id,
            client_operation_id=client_operation_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            response_payload=response_payload or {},
            created_at=datetime.now(UTC),
        )
    )


async def create_template(session: AsyncSession, context: AuthContext, payload):
    template = ChecklistTemplate(
        tenant_id=context.tenant.id,
        name=payload.name,
        station_type=payload.station_type,
        version=payload.version,
    )
    session.add(template)
    await session.flush()
    for item in payload.items:
        session.add(
            ChecklistTemplateItem(
                tenant_id=context.tenant.id,
                template_id=template.id,
                code=item.code,
                label=item.label,
                item_type=item.item_type.value,
                required=item.required,
                sort_order=item.sort_order,
                config=item.config,
            )
        )
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


async def list_templates(
    session: AsyncSession,
    context: AuthContext,
    *,
    active_only: bool = True,
) -> list[ChecklistTemplate]:
    stmt = select(ChecklistTemplate).where(ChecklistTemplate.tenant_id == context.tenant.id)
    if active_only:
        stmt = stmt.where(ChecklistTemplate.is_active.is_(True))
    stmt = stmt.order_by(ChecklistTemplate.name, ChecklistTemplate.version.desc())
    return list((await session.execute(stmt)).scalars().all())


async def get_template_detail(
    session: AsyncSession,
    context: AuthContext,
    template_id: UUID,
) -> tuple[ChecklistTemplate, list[ChecklistTemplateItem]]:
    template = await tenant_get_or_404(
        session, ChecklistTemplate, context.tenant.id, template_id
    )
    items = list(
        (
            await session.execute(
                select(ChecklistTemplateItem)
                .where(
                    ChecklistTemplateItem.tenant_id == context.tenant.id,
                    ChecklistTemplateItem.template_id == template.id,
                )
                .order_by(ChecklistTemplateItem.sort_order, ChecklistTemplateItem.code)
            )
        )
        .scalars()
        .all()
    )
    return template, items


async def validate_assignee(
    session: AsyncSession,
    context: AuthContext,
    user_id: UUID,
) -> None:
    membership = (
        await session.execute(
            select(Membership).where(
                Membership.tenant_id == context.tenant.id,
                Membership.user_id == user_id,
                Membership.is_active.is_(True),
                Membership.role.in_(
                    [
                        Role.TECNICO.value,
                        Role.SUPERVISOR.value,
                        Role.GESTOR.value,
                    ]
                ),
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assignee_not_found")


async def create_visit(session: AsyncSession, context: AuthContext, payload) -> Visit:
    station = await tenant_get_or_404(session, Station, context.tenant.id, payload.station_id)
    if not station.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="station_inactive")
    template = await tenant_get_or_404(
        session, ChecklistTemplate, context.tenant.id, payload.checklist_template_id
    )
    if not template.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="template_inactive")
    await validate_assignee(session, context, payload.assigned_user_id)

    visit = Visit(
        tenant_id=context.tenant.id,
        station_id=payload.station_id,
        assigned_user_id=payload.assigned_user_id,
        checklist_template_id=payload.checklist_template_id,
        scheduled_for=payload.scheduled_for,
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


async def get_visit_for_context(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
) -> Visit:
    visit = await tenant_get_or_404(session, Visit, context.tenant.id, visit_id)
    if context.membership.role == Role.TECNICO.value and visit.assigned_user_id != context.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return visit


async def list_visits(
    session: AsyncSession,
    context: AuthContext,
    *,
    visit_status: str | None,
    scheduled_from: datetime | None,
    scheduled_to: datetime | None,
    limit: int,
    offset: int,
) -> list[Visit]:
    stmt = select(Visit).where(Visit.tenant_id == context.tenant.id)
    if context.membership.role == Role.TECNICO.value:
        stmt = stmt.where(Visit.assigned_user_id == context.user.id)
    if visit_status is not None:
        stmt = stmt.where(Visit.status == visit_status)
    if scheduled_from is not None:
        stmt = stmt.where(Visit.scheduled_for >= scheduled_from)
    if scheduled_to is not None:
        stmt = stmt.where(Visit.scheduled_for <= scheduled_to)
    stmt = stmt.order_by(Visit.scheduled_for).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def start_visit(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    client_operation_id: UUID,
) -> Visit:
    receipt = await get_receipt(
        session,
        tenant_id=context.tenant.id,
        client_operation_id=client_operation_id,
        action="VISIT_START",
    )
    visit = await get_visit_for_context(session, context, visit_id)
    if receipt is not None:
        return visit
    if visit.status not in {VisitStatus.PROGRAMADA.value, VisitStatus.DEVOLVIDA.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_cannot_start")

    visit.status = VisitStatus.EM_EXECUCAO.value
    visit.started_at = datetime.now(UTC)
    visit.revision += 1
    save_receipt(
        session,
        context,
        client_operation_id=client_operation_id,
        action="VISIT_START",
        entity_type="visit",
        entity_id=visit.id,
    )
    add_audit(
        session,
        context,
        action="VISIT_START",
        entity_type="visit",
        entity_id=visit.id,
    )
    await session.commit()
    await session.refresh(visit)
    return visit


async def save_answers(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload,
) -> SyncAck:
    receipt = await get_receipt(
        session,
        tenant_id=context.tenant.id,
        client_operation_id=payload.client_operation_id,
        action="VISIT_ANSWERS",
    )
    visit = await get_visit_for_context(session, context, visit_id)
    if receipt is not None:
        return SyncAck(
            client_operation_id=payload.client_operation_id,
            duplicate=True,
            entity_id=visit.id,
            action="VISIT_ANSWERS",
        )
    if visit.status != VisitStatus.EM_EXECUCAO.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_not_in_progress")

    item_ids = {answer.item_id for answer in payload.answers}
    valid_items = set(
        (
            await session.execute(
                select(ChecklistTemplateItem.id).where(
                    ChecklistTemplateItem.tenant_id == context.tenant.id,
                    ChecklistTemplateItem.template_id == visit.checklist_template_id,
                    ChecklistTemplateItem.id.in_(item_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    if valid_items != item_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_item")

    for answer in payload.answers:
        existing = (
            await session.execute(
                select(VisitAnswer).where(
                    VisitAnswer.tenant_id == context.tenant.id,
                    VisitAnswer.visit_id == visit.id,
                    VisitAnswer.item_id == answer.item_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                VisitAnswer(
                    tenant_id=context.tenant.id,
                    visit_id=visit.id,
                    item_id=answer.item_id,
                    value=answer.value,
                    note=answer.note,
                )
            )
        else:
            existing.value = answer.value
            existing.note = answer.note

    visit.revision += 1
    save_receipt(
        session,
        context,
        client_operation_id=payload.client_operation_id,
        action="VISIT_ANSWERS",
        entity_type="visit",
        entity_id=visit.id,
    )
    add_audit(
        session,
        context,
        action="VISIT_ANSWERS",
        entity_type="visit",
        entity_id=visit.id,
        fields=["answers"],
    )
    await session.commit()
    return SyncAck(
        client_operation_id=payload.client_operation_id,
        duplicate=False,
        entity_id=visit.id,
        action="VISIT_ANSWERS",
    )


async def save_measurements(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload,
) -> SyncAck:
    receipt = await get_receipt(
        session,
        tenant_id=context.tenant.id,
        client_operation_id=payload.client_operation_id,
        action="VISIT_MEASUREMENTS",
    )
    visit = await get_visit_for_context(session, context, visit_id)
    if receipt is not None:
        return SyncAck(
            client_operation_id=payload.client_operation_id,
            duplicate=True,
            entity_id=visit.id,
            action="VISIT_MEASUREMENTS",
        )
    if visit.status != VisitStatus.EM_EXECUCAO.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_not_in_progress")

    for measurement in payload.measurements:
        session.add(
            Measurement(
                tenant_id=context.tenant.id,
                visit_id=visit.id,
                measurement_type=measurement.measurement_type,
                status=measurement.status.value,
                value=measurement.value,
                unit=measurement.unit,
                reason=measurement.reason,
                taken_at=measurement.taken_at,
            )
        )

    visit.revision += 1
    save_receipt(
        session,
        context,
        client_operation_id=payload.client_operation_id,
        action="VISIT_MEASUREMENTS",
        entity_type="visit",
        entity_id=visit.id,
    )
    add_audit(
        session,
        context,
        action="VISIT_MEASUREMENTS",
        entity_type="visit",
        entity_id=visit.id,
        fields=["measurements"],
    )
    await session.commit()
    return SyncAck(
        client_operation_id=payload.client_operation_id,
        duplicate=False,
        entity_id=visit.id,
        action="VISIT_MEASUREMENTS",
    )


async def list_measurements(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
) -> list[Measurement]:
    visit = await get_visit_for_context(session, context, visit_id)
    return list(
        (
            await session.execute(
                select(Measurement)
                .where(
                    Measurement.tenant_id == context.tenant.id,
                    Measurement.visit_id == visit.id,
                )
                .order_by(Measurement.taken_at)
            )
        )
        .scalars()
        .all()
    )


async def finish_visit(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload,
) -> Visit:
    receipt = await get_receipt(
        session,
        tenant_id=context.tenant.id,
        client_operation_id=payload.client_operation_id,
        action="VISIT_FINISH",
    )
    visit = await get_visit_for_context(session, context, visit_id)
    if receipt is not None:
        return visit
    if visit.status != VisitStatus.EM_EXECUCAO.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_not_in_progress")

    required_ids = set(
        (
            await session.execute(
                select(ChecklistTemplateItem.id).where(
                    ChecklistTemplateItem.tenant_id == context.tenant.id,
                    ChecklistTemplateItem.template_id == visit.checklist_template_id,
                    ChecklistTemplateItem.required.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    answered_ids = set(
        (
            await session.execute(
                select(VisitAnswer.item_id).where(
                    VisitAnswer.tenant_id == context.tenant.id,
                    VisitAnswer.visit_id == visit.id,
                    VisitAnswer.item_id.in_(required_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    if answered_ids != required_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="required_checklist_incomplete",
        )

    visit.status = VisitStatus.AGUARDANDO_REVISAO.value
    visit.finished_at = datetime.now(UTC)
    if payload.notes is not None:
        visit.notes = payload.notes
    visit.revision += 1
    save_receipt(
        session,
        context,
        client_operation_id=payload.client_operation_id,
        action="VISIT_FINISH",
        entity_type="visit",
        entity_id=visit.id,
    )
    add_audit(
        session,
        context,
        action="VISIT_FINISH",
        entity_type="visit",
        entity_id=visit.id,
    )
    await session.commit()
    await session.refresh(visit)
    return visit
