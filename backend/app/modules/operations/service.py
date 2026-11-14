from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import Visit, VisitStatus
from app.models.identity import Membership, Role
from app.models.maintenance import (
    MaintenancePlan,
    Occurrence,
    OccurrenceStatus,
    ReviewDecision,
    VisitReview,
    WorkOrder,
    WorkOrderPriority,
    WorkOrderStatus,
    WorkOrderStatusHistory,
)
from app.models.operations import Asset, AssetStatus, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit, tenant_get_or_404
from app.modules.field.service import get_accessible_visit, get_tenant_membership
from app.modules.operations.schemas import (
    OccurrenceCreate,
    VisitReviewCreate,
    WorkOrderAssign,
    WorkOrderCreate,
    WorkOrderTransition,
)

MANAGEMENT_ROLES = {
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
}
FIELD_ROLES = {Role.TECNICO.value, Role.MANUTENCAO.value}

SLA_HOURS = {
    WorkOrderPriority.CRITICA.value: 8,
    WorkOrderPriority.ALTA.value: 24,
    WorkOrderPriority.MEDIA.value: 72,
    WorkOrderPriority.BAIXA.value: 168,
}

ALLOWED_TRANSITIONS = {
    WorkOrderStatus.ABERTA.value: {
        WorkOrderStatus.TRIAGEM.value,
        WorkOrderStatus.PLANEJADA.value,
        WorkOrderStatus.CANCELADA.value,
    },
    WorkOrderStatus.TRIAGEM.value: {
        WorkOrderStatus.PLANEJADA.value,
        WorkOrderStatus.CANCELADA.value,
    },
    WorkOrderStatus.PLANEJADA.value: {
        WorkOrderStatus.EM_EXECUCAO.value,
        WorkOrderStatus.AGUARDANDO_MATERIAL.value,
        WorkOrderStatus.AGUARDANDO_TERCEIRO.value,
        WorkOrderStatus.CANCELADA.value,
    },
    WorkOrderStatus.EM_EXECUCAO.value: {
        WorkOrderStatus.AGUARDANDO_MATERIAL.value,
        WorkOrderStatus.AGUARDANDO_TERCEIRO.value,
        WorkOrderStatus.CONCLUIDA.value,
        WorkOrderStatus.CANCELADA.value,
    },
    WorkOrderStatus.AGUARDANDO_MATERIAL.value: {
        WorkOrderStatus.EM_EXECUCAO.value,
        WorkOrderStatus.CONCLUIDA.value,
        WorkOrderStatus.CANCELADA.value,
    },
    WorkOrderStatus.AGUARDANDO_TERCEIRO.value: {
        WorkOrderStatus.EM_EXECUCAO.value,
        WorkOrderStatus.CONCLUIDA.value,
        WorkOrderStatus.CANCELADA.value,
    },
    WorkOrderStatus.CONCLUIDA.value: {
        WorkOrderStatus.VALIDADA.value,
        WorkOrderStatus.EM_EXECUCAO.value,
    },
    WorkOrderStatus.VALIDADA.value: set(),
    WorkOrderStatus.CANCELADA.value: set(),
}


async def create_occurrence(
    session: AsyncSession,
    context: AuthContext,
    payload: OccurrenceCreate,
) -> Occurrence:
    station = await tenant_get_or_404(
        session, Station, context.tenant.id, payload.station_id
    )

    visit = None
    if payload.visit_id is not None:
        visit = await get_accessible_visit(session, context, payload.visit_id)
        if visit.station_id != station.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="visit_station_mismatch",
            )
    elif context.membership.role in FIELD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="field_occurrence_requires_visit",
        )

    if payload.asset_id is not None:
        asset = await tenant_get_or_404(
            session, Asset, context.tenant.id, payload.asset_id
        )
        if asset.station_id != station.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="asset_station_mismatch",
            )

    occurrence = Occurrence(
        tenant_id=context.tenant.id,
        visit_id=payload.visit_id,
        station_id=station.id,
        asset_id=payload.asset_id,
        occurrence_type=payload.occurrence_type.strip(),
        severity=payload.severity.value,
        status=OccurrenceStatus.ABERTA.value,
        description=payload.description.strip(),
        detected_at=payload.detected_at,
        created_by_user_id=context.user.id,
    )
    session.add(occurrence)
    await session.flush()
    add_audit(
        session,
        context,
        action="OCCURRENCE_CREATE",
        entity_type="occurrence",
        entity_id=occurrence.id,
    )
    await session.commit()
    await session.refresh(occurrence)
    return occurrence


async def list_occurrences(
    session: AsyncSession,
    context: AuthContext,
    *,
    occurrence_status: str | None = None,
    severity: str | None = None,
    station_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Occurrence]:
    stmt = select(Occurrence).where(Occurrence.tenant_id == context.tenant.id)
    if context.membership.role in FIELD_ROLES:
        stmt = stmt.where(Occurrence.created_by_user_id == context.user.id)
    if occurrence_status is not None:
        stmt = stmt.where(Occurrence.status == occurrence_status)
    if severity is not None:
        stmt = stmt.where(Occurrence.severity == severity)
    if station_id is not None:
        stmt = stmt.where(Occurrence.station_id == station_id)
    stmt = stmt.order_by(Occurrence.detected_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def tenant_occurrence_or_404(
    session: AsyncSession,
    tenant_id: UUID,
    occurrence_id: UUID,
) -> Occurrence:
    return await tenant_get_or_404(session, Occurrence, tenant_id, occurrence_id)


async def _validate_assignment(
    session: AsyncSession,
    tenant_id: UUID,
    membership_id: UUID | None,
) -> Membership | None:
    if membership_id is None:
        return None
    membership = await get_tenant_membership(session, tenant_id, membership_id)
    if membership.role not in {
        Role.TECNICO.value,
        Role.MANUTENCAO.value,
        Role.SUPERVISOR.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="membership_cannot_receive_work_order",
        )
    return membership


async def create_work_order(
    session: AsyncSession,
    context: AuthContext,
    payload: WorkOrderCreate,
) -> WorkOrder:
    occurrence = None
    station_id = payload.station_id
    asset_id = payload.asset_id

    if payload.occurrence_id is not None:
        occurrence = await tenant_occurrence_or_404(
            session, context.tenant.id, payload.occurrence_id
        )
        if station_id is not None and station_id != occurrence.station_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="occurrence_station_mismatch",
            )
        if asset_id is not None and occurrence.asset_id is not None and asset_id != occurrence.asset_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="occurrence_asset_mismatch",
            )
        station_id = occurrence.station_id
        asset_id = asset_id or occurrence.asset_id

    if station_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="station_id_required",
        )

    station = await tenant_get_or_404(session, Station, context.tenant.id, station_id)
    if asset_id is not None:
        asset = await tenant_get_or_404(session, Asset, context.tenant.id, asset_id)
        if asset.station_id != station.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="asset_station_mismatch",
            )
    await _validate_assignment(
        session, context.tenant.id, payload.assigned_membership_id
    )

    now = datetime.now(UTC)
    priority = payload.priority.value
    work_order = WorkOrder(
        tenant_id=context.tenant.id,
        occurrence_id=payload.occurrence_id,
        station_id=station.id,
        asset_id=asset_id,
        assigned_membership_id=payload.assigned_membership_id,
        priority=priority,
        status=WorkOrderStatus.ABERTA.value,
        description=payload.description.strip(),
        sla_due_at=now + timedelta(hours=SLA_HOURS[priority]),
    )
    session.add(work_order)
    await session.flush()
    session.add(
        WorkOrderStatusHistory(
            tenant_id=context.tenant.id,
            work_order_id=work_order.id,
            from_status=None,
            to_status=WorkOrderStatus.ABERTA.value,
            changed_by_user_id=context.user.id,
            note="OS criada",
            changed_at=now,
        )
    )
    if occurrence is not None:
        occurrence.status = OccurrenceStatus.TRIADA.value

    add_audit(
        session,
        context,
        action="WORK_ORDER_CREATE",
        entity_type="work_order",
        entity_id=work_order.id,
    )
    await session.commit()
    await session.refresh(work_order)
    return work_order


async def get_accessible_work_order(
    session: AsyncSession,
    context: AuthContext,
    work_order_id: UUID,
) -> WorkOrder:
    stmt = select(WorkOrder).where(
        WorkOrder.id == work_order_id,
        WorkOrder.tenant_id == context.tenant.id,
    )
    if context.membership.role in FIELD_ROLES:
        stmt = stmt.where(WorkOrder.assigned_membership_id == context.membership.id)
    work_order = (await session.execute(stmt)).scalar_one_or_none()
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="work_order_not_found")
    return work_order


async def list_work_orders(
    session: AsyncSession,
    context: AuthContext,
    *,
    work_order_status: str | None = None,
    priority: str | None = None,
    overdue_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[WorkOrder]:
    stmt = select(WorkOrder).where(WorkOrder.tenant_id == context.tenant.id)
    if context.membership.role in FIELD_ROLES:
        stmt = stmt.where(WorkOrder.assigned_membership_id == context.membership.id)
    if work_order_status is not None:
        stmt = stmt.where(WorkOrder.status == work_order_status)
    if priority is not None:
        stmt = stmt.where(WorkOrder.priority == priority)
    if overdue_only:
        stmt = stmt.where(
            WorkOrder.sla_due_at < datetime.now(UTC),
            WorkOrder.status.notin_(
                [WorkOrderStatus.VALIDADA.value, WorkOrderStatus.CANCELADA.value]
            ),
        )
    stmt = stmt.order_by(WorkOrder.sla_due_at).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def assign_work_order(
    session: AsyncSession,
    context: AuthContext,
    work_order_id: UUID,
    payload: WorkOrderAssign,
) -> WorkOrder:
    work_order = await tenant_get_or_404(
        session, WorkOrder, context.tenant.id, work_order_id
    )
    await _validate_assignment(
        session, context.tenant.id, payload.assigned_membership_id
    )
    work_order.assigned_membership_id = payload.assigned_membership_id
    add_audit(
        session,
        context,
        action="WORK_ORDER_ASSIGN",
        entity_type="work_order",
        entity_id=work_order.id,
    )
    await session.commit()
    await session.refresh(work_order)
    return work_order


async def transition_work_order(
    session: AsyncSession,
    context: AuthContext,
    work_order_id: UUID,
    payload: WorkOrderTransition,
) -> WorkOrder:
    work_order = await get_accessible_work_order(session, context, work_order_id)
    target = payload.status.value
    allowed = ALLOWED_TRANSITIONS.get(work_order.status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="invalid_work_order_transition",
        )

    if context.membership.role in FIELD_ROLES and target in {
        WorkOrderStatus.VALIDADA.value,
        WorkOrderStatus.CANCELADA.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="field_role_cannot_validate_or_cancel",
        )

    now = datetime.now(UTC)
    previous = work_order.status
    work_order.status = target
    if target == WorkOrderStatus.EM_EXECUCAO.value and work_order.started_at is None:
        work_order.started_at = now
    if target == WorkOrderStatus.CONCLUIDA.value:
        work_order.completed_at = now
    if target == WorkOrderStatus.VALIDADA.value:
        work_order.validated_at = now

    session.add(
        WorkOrderStatusHistory(
            tenant_id=context.tenant.id,
            work_order_id=work_order.id,
            from_status=previous,
            to_status=target,
            changed_by_user_id=context.user.id,
            note=payload.note,
            changed_at=now,
        )
    )
    add_audit(
        session,
        context,
        action="WORK_ORDER_TRANSITION",
        entity_type="work_order",
        entity_id=work_order.id,
        fields=["status"],
    )

    if target == WorkOrderStatus.VALIDADA.value and work_order.occurrence_id is not None:
        occurrence = await tenant_occurrence_or_404(
            session, context.tenant.id, work_order.occurrence_id
        )
        occurrence.status = OccurrenceStatus.RESOLVIDA.value

    await session.commit()
    await session.refresh(work_order)
    return work_order


async def work_order_history(
    session: AsyncSession,
    context: AuthContext,
    work_order_id: UUID,
) -> list[WorkOrderStatusHistory]:
    await get_accessible_work_order(session, context, work_order_id)
    stmt = (
        select(WorkOrderStatusHistory)
        .where(
            WorkOrderStatusHistory.tenant_id == context.tenant.id,
            WorkOrderStatusHistory.work_order_id == work_order_id,
        )
        .order_by(WorkOrderStatusHistory.changed_at)
    )
    return list((await session.execute(stmt)).scalars().all())


async def review_visit(
    session: AsyncSession,
    context: AuthContext,
    visit_id: UUID,
    payload: VisitReviewCreate,
) -> VisitReview:
    visit = await tenant_get_or_404(session, Visit, context.tenant.id, visit_id)
    if visit.status != VisitStatus.AGUARDANDO_REVISAO.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="visit_not_waiting_review",
        )

    now = datetime.now(UTC)
    review = VisitReview(
        tenant_id=context.tenant.id,
        visit_id=visit.id,
        reviewer_user_id=context.user.id,
        decision=payload.decision.value,
        notes=payload.notes,
        reviewed_at=now,
    )
    session.add(review)
    visit.status = (
        VisitStatus.REVISADA.value
        if payload.decision == ReviewDecision.APROVAR
        else VisitStatus.DEVOLVIDA.value
    )
    await session.flush()
    add_audit(
        session,
        context,
        action="VISIT_REVIEW",
        entity_type="visit",
        entity_id=visit.id,
        fields=["status"],
    )
    await session.commit()
    await session.refresh(review)
    return review


async def dashboard_overview(
    session: AsyncSession,
    context: AuthContext,
) -> dict[str, int]:
    tenant_id = context.tenant.id
    active_stations = await session.scalar(
        select(func.count(Station.id)).where(
            Station.tenant_id == tenant_id,
            Station.is_active.is_(True),
        )
    )
    unavailable_assets = await session.scalar(
        select(func.count(Asset.id)).where(
            Asset.tenant_id == tenant_id,
            Asset.is_active.is_(True),
            Asset.status.notin_(
                [
                    AssetStatus.OPERANDO.value,
                    AssetStatus.NAO_POSSUI.value,
                    AssetStatus.NAO_APLICAVEL.value,
                ]
            ),
        )
    )
    visits_waiting_review = await session.scalar(
        select(func.count(Visit.id)).where(
            Visit.tenant_id == tenant_id,
            Visit.status == VisitStatus.AGUARDANDO_REVISAO.value,
        )
    )
    open_occurrences = await session.scalar(
        select(func.count(Occurrence.id)).where(
            Occurrence.tenant_id == tenant_id,
            Occurrence.status.notin_(
                [OccurrenceStatus.RESOLVIDA.value, OccurrenceStatus.CANCELADA.value]
            ),
        )
    )
    open_statuses = [
        value.value
        for value in WorkOrderStatus
        if value not in {WorkOrderStatus.VALIDADA, WorkOrderStatus.CANCELADA}
    ]
    open_work_orders = await session.scalar(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.status.in_(open_statuses),
        )
    )
    overdue_work_orders = await session.scalar(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.status.in_(open_statuses),
            WorkOrder.sla_due_at < datetime.now(UTC),
        )
    )
    critical_work_orders = await session.scalar(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.status.in_(open_statuses),
            WorkOrder.priority == WorkOrderPriority.CRITICA.value,
        )
    )
    return {
        "active_stations": int(active_stations or 0),
        "unavailable_assets": int(unavailable_assets or 0),
        "visits_waiting_review": int(visits_waiting_review or 0),
        "open_occurrences": int(open_occurrences or 0),
        "open_work_orders": int(open_work_orders or 0),
        "overdue_work_orders": int(overdue_work_orders or 0),
        "critical_work_orders": int(critical_work_orders or 0),
    }


async def dashboard_sla(
    session: AsyncSession,
    context: AuthContext,
) -> list[dict[str, int | str]]:
    tenant_id = context.tenant.id
    now = datetime.now(UTC)
    closed = [WorkOrderStatus.VALIDADA.value, WorkOrderStatus.CANCELADA.value]
    buckets: list[dict[str, int | str]] = []
    for priority in WorkOrderPriority:
        open_count = await session.scalar(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.priority == priority.value,
                WorkOrder.status.notin_(closed),
            )
        )
        overdue_count = await session.scalar(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.priority == priority.value,
                WorkOrder.status.notin_(closed),
                WorkOrder.sla_due_at < now,
            )
        )
        buckets.append(
            {
                "priority": priority.value,
                "open_count": int(open_count or 0),
                "overdue_count": int(overdue_count or 0),
            }
        )
    return buckets


async def operational_alerts(
    session: AsyncSession,
    context: AuthContext,
) -> list[dict]:
    now = datetime.now(UTC)
    alerts: list[dict] = []

    overdue_visits = list(
        (
            await session.execute(
                select(Visit).where(
                    Visit.tenant_id == context.tenant.id,
                    Visit.status == VisitStatus.PROGRAMADA.value,
                    Visit.scheduled_for < now,
                )
            )
        ).scalars()
    )
    for visit in overdue_visits:
        alerts.append(
            {
                "kind": "VISIT_OVERDUE",
                "severity": "ALTA",
                "title": "Visita atrasada",
                "message": "Visita programada ainda não foi iniciada.",
                "entity_type": "visit",
                "entity_id": visit.id,
                "due_at": visit.scheduled_for,
            }
        )

    overdue_orders = list(
        (
            await session.execute(
                select(WorkOrder).where(
                    WorkOrder.tenant_id == context.tenant.id,
                    WorkOrder.sla_due_at < now,
                    WorkOrder.status.notin_(
                        [WorkOrderStatus.VALIDADA.value, WorkOrderStatus.CANCELADA.value]
                    ),
                )
            )
        ).scalars()
    )
    for order in overdue_orders:
        alerts.append(
            {
                "kind": "WORK_ORDER_SLA",
                "severity": "CRITICA" if order.priority == WorkOrderPriority.CRITICA.value else "ALTA",
                "title": "OS fora do SLA",
                "message": order.description,
                "entity_type": "work_order",
                "entity_id": order.id,
                "due_at": order.sla_due_at,
            }
        )

    overdue_maintenance = list(
        (
            await session.execute(
                select(MaintenancePlan).where(
                    MaintenancePlan.tenant_id == context.tenant.id,
                    MaintenancePlan.is_active.is_(True),
                    MaintenancePlan.next_due_at < now,
                )
            )
        ).scalars()
    )
    for plan in overdue_maintenance:
        alerts.append(
            {
                "kind": "MAINTENANCE_OVERDUE",
                "severity": "ALTA",
                "title": "Manutenção preventiva vencida",
                "message": plan.instructions or "Plano preventivo vencido.",
                "entity_type": "maintenance_plan",
                "entity_id": plan.id,
                "due_at": plan.next_due_at,
            }
        )

    waiting_reviews = list(
        (
            await session.execute(
                select(Visit).where(
                    Visit.tenant_id == context.tenant.id,
                    Visit.status == VisitStatus.AGUARDANDO_REVISAO.value,
                )
            )
        ).scalars()
    )
    for visit in waiting_reviews:
        alerts.append(
            {
                "kind": "VISIT_REVIEW",
                "severity": "MEDIA",
                "title": "Visita aguardando revisão",
                "message": "Dados de campo aguardam validação da supervisão.",
                "entity_type": "visit",
                "entity_id": visit.id,
                "due_at": visit.finished_at,
            }
        )

    severity_rank = {"CRITICA": 0, "ALTA": 1, "MEDIA": 2, "BAIXA": 3}
    alerts.sort(
        key=lambda item: (
            severity_rank.get(item["severity"], 9),
            item["due_at"] or now,
        )
    )
    return alerts[:200]
