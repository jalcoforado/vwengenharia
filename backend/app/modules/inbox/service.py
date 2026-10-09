from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import Visit, VisitStatus
from app.models.identity import Role
from app.models.maintenance import MaintenancePlan, WorkOrder, WorkOrderStatus
from app.models.materials import MaterialRequest, RequestStatus
from app.modules.auth.dependencies import AuthContext

FIELD_ROLES = {Role.TECNICO.value, Role.MANUTENCAO.value}
MANAGEMENT_ROLES = {
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
}


def _priority_rank(priority: str) -> int:
    return {
        "CRITICA": 0,
        "ALTA": 1,
        "MEDIA": 2,
        "BAIXA": 3,
    }.get(priority, 4)


async def build_inbox(
    session: AsyncSession,
    context: AuthContext,
) -> list[dict]:
    now = datetime.now(UTC)
    items: list[dict] = []
    role = context.membership.role

    if role in FIELD_ROLES:
        visits = list(
            (
                await session.execute(
                    select(Visit).where(
                        Visit.tenant_id == context.tenant.id,
                        Visit.technician_membership_id == context.membership.id,
                        Visit.status.in_(
                            [
                                VisitStatus.PROGRAMADA.value,
                                VisitStatus.EM_EXECUCAO.value,
                                VisitStatus.DEVOLVIDA.value,
                            ]
                        ),
                    )
                )
            ).scalars()
        )
        for visit in visits:
            overdue = (
                visit.status == VisitStatus.PROGRAMADA.value
                and visit.scheduled_for < now
            )
            items.append(
                {
                    "kind": "VISIT",
                    "priority": "ALTA" if overdue or visit.status == VisitStatus.DEVOLVIDA.value else "MEDIA",
                    "title": (
                        "Visita devolvida"
                        if visit.status == VisitStatus.DEVOLVIDA.value
                        else "Visita atrasada"
                        if overdue
                        else "Visita programada"
                    ),
                    "message": (
                        "A supervisão devolveu a visita para ajustes."
                        if visit.status == VisitStatus.DEVOLVIDA.value
                        else "Visita de campo atribuída a você."
                    ),
                    "entity_type": "visit",
                    "entity_id": visit.id,
                    "due_at": visit.scheduled_for,
                    "status": visit.status,
                }
            )

        work_orders = list(
            (
                await session.execute(
                    select(WorkOrder).where(
                        WorkOrder.tenant_id == context.tenant.id,
                        WorkOrder.assigned_membership_id == context.membership.id,
                        WorkOrder.status.notin_(
                            [
                                WorkOrderStatus.VALIDADA.value,
                                WorkOrderStatus.CANCELADA.value,
                            ]
                        ),
                    )
                )
            ).scalars()
        )
        for order in work_orders:
            items.append(
                {
                    "kind": "WORK_ORDER",
                    "priority": order.priority,
                    "title": "Ordem de serviço atribuída",
                    "message": order.description,
                    "entity_type": "work_order",
                    "entity_id": order.id,
                    "due_at": order.sla_due_at,
                    "status": order.status,
                }
            )

        maintenance = list(
            (
                await session.execute(
                    select(MaintenancePlan).where(
                        MaintenancePlan.tenant_id == context.tenant.id,
                        MaintenancePlan.assigned_membership_id == context.membership.id,
                        MaintenancePlan.is_active.is_(True),
                        MaintenancePlan.next_due_at <= now + timedelta(days=7),
                    )
                )
            ).scalars()
        )
        for plan in maintenance:
            overdue = plan.next_due_at < now
            items.append(
                {
                    "kind": "MAINTENANCE",
                    "priority": "ALTA" if overdue else "MEDIA",
                    "title": "Preventiva vencida" if overdue else "Preventiva próxima",
                    "message": plan.instructions or "Executar manutenção preventiva do ativo.",
                    "entity_type": "maintenance_plan",
                    "entity_id": plan.id,
                    "due_at": plan.next_due_at,
                    "status": "VENCIDA" if overdue else "PROGRAMADA",
                }
            )

        requests = list(
            (
                await session.execute(
                    select(MaterialRequest).where(
                        MaterialRequest.tenant_id == context.tenant.id,
                        MaterialRequest.requested_by_user_id == context.user.id,
                        MaterialRequest.status.notin_(
                            [
                                RequestStatus.ATENDIDA.value,
                                RequestStatus.CANCELADA.value,
                            ]
                        ),
                    )
                )
            ).scalars()
        )
        for request in requests:
            items.append(
                {
                    "kind": "MATERIAL_REQUEST",
                    "priority": request.priority,
                    "title": "Solicitação em andamento",
                    "message": request.item_name,
                    "entity_type": "material_request",
                    "entity_id": request.id,
                    "due_at": None,
                    "status": request.status,
                }
            )

    if role in MANAGEMENT_ROLES:
        reviews = list(
            (
                await session.execute(
                    select(Visit).where(
                        Visit.tenant_id == context.tenant.id,
                        Visit.status == VisitStatus.AGUARDANDO_REVISAO.value,
                    )
                )
            ).scalars()
        )
        for visit in reviews:
            items.append(
                {
                    "kind": "VISIT_REVIEW",
                    "priority": "MEDIA",
                    "title": "Visita aguardando revisão",
                    "message": "Validar os dados enviados pela equipe de campo.",
                    "entity_type": "visit",
                    "entity_id": visit.id,
                    "due_at": visit.finished_at,
                    "status": visit.status,
                }
            )

        critical_orders = list(
            (
                await session.execute(
                    select(WorkOrder).where(
                        WorkOrder.tenant_id == context.tenant.id,
                        WorkOrder.status.notin_(
                            [
                                WorkOrderStatus.VALIDADA.value,
                                WorkOrderStatus.CANCELADA.value,
                            ]
                        ),
                    )
                )
            ).scalars()
        )
        for order in critical_orders:
            if order.priority == "CRITICA" or order.sla_due_at < now:
                items.append(
                    {
                        "kind": "WORK_ORDER_MANAGEMENT",
                        "priority": "CRITICA" if order.sla_due_at < now else order.priority,
                        "title": "OS fora do SLA" if order.sla_due_at < now else "OS crítica",
                        "message": order.description,
                        "entity_type": "work_order",
                        "entity_id": order.id,
                        "due_at": order.sla_due_at,
                        "status": order.status,
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
            items.append(
                {
                    "kind": "MAINTENANCE_MANAGEMENT",
                    "priority": "ALTA",
                    "title": "Preventiva vencida",
                    "message": plan.instructions or "Plano preventivo vencido.",
                    "entity_type": "maintenance_plan",
                    "entity_id": plan.id,
                    "due_at": plan.next_due_at,
                    "status": "VENCIDA",
                }
            )

        material_requests = list(
            (
                await session.execute(
                    select(MaterialRequest).where(
                        MaterialRequest.tenant_id == context.tenant.id,
                        MaterialRequest.status.in_(
                            [
                                RequestStatus.SOLICITADA.value,
                                RequestStatus.APROVADA.value,
                            ]
                        ),
                    )
                )
            ).scalars()
        )
        for request in material_requests:
            items.append(
                {
                    "kind": "MATERIAL_MANAGEMENT",
                    "priority": request.priority,
                    "title": "Solicitação pendente",
                    "message": request.item_name,
                    "entity_type": "material_request",
                    "entity_id": request.id,
                    "due_at": None,
                    "status": request.status,
                }
            )

    items.sort(
        key=lambda item: (
            _priority_rank(item["priority"]),
            item["due_at"] or now + timedelta(days=3650),
        )
    )
    return items[:200]
