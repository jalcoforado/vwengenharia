import csv
from datetime import UTC, datetime
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select

from app.models.field import Visit
from app.models.identity import Role
from app.models.maintenance import MaintenancePlan, WorkOrder
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles

router = APIRouter(prefix="/reports", tags=["relatorios"])

MANAGEMENT_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
)
ManagementContextDep = Annotated[AuthContext, Depends(require_roles(*MANAGEMENT_ROLES))]


def csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(headers)
    writer.writerows(rows)
    body = "\ufeff" + output.getvalue()
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/visits.csv")
async def visits_csv(
    context: ManagementContextDep,
    session: SessionDep,
) -> Response:
    rows = list(
        (
            await session.execute(
                select(Visit)
                .where(Visit.tenant_id == context.tenant.id)
                .order_by(Visit.scheduled_for.desc())
                .limit(10_000)
            )
        ).scalars()
    )
    return csv_response(
        "visitas.csv",
        [
            "id",
            "station_id",
            "technician_membership_id",
            "scheduled_for",
            "started_at",
            "finished_at",
            "status",
            "notes",
        ],
        [
            [
                item.id,
                item.station_id,
                item.technician_membership_id,
                item.scheduled_for,
                item.started_at or "",
                item.finished_at or "",
                item.status,
                item.notes or "",
            ]
            for item in rows
        ],
    )


@router.get("/work-orders.csv")
async def work_orders_csv(
    context: ManagementContextDep,
    session: SessionDep,
) -> Response:
    rows = list(
        (
            await session.execute(
                select(WorkOrder)
                .where(WorkOrder.tenant_id == context.tenant.id)
                .order_by(WorkOrder.created_at.desc())
                .limit(10_000)
            )
        ).scalars()
    )
    return csv_response(
        "ordens-servico.csv",
        [
            "id",
            "station_id",
            "asset_id",
            "assigned_membership_id",
            "priority",
            "status",
            "sla_due_at",
            "started_at",
            "completed_at",
            "validated_at",
            "description",
        ],
        [
            [
                item.id,
                item.station_id,
                item.asset_id or "",
                item.assigned_membership_id or "",
                item.priority,
                item.status,
                item.sla_due_at,
                item.started_at or "",
                item.completed_at or "",
                item.validated_at or "",
                item.description,
            ]
            for item in rows
        ],
    )


@router.get("/maintenance.csv")
async def maintenance_csv(
    context: ManagementContextDep,
    session: SessionDep,
) -> Response:
    now = datetime.now(UTC)
    rows = list(
        (
            await session.execute(
                select(MaintenancePlan)
                .where(MaintenancePlan.tenant_id == context.tenant.id)
                .order_by(MaintenancePlan.next_due_at)
                .limit(10_000)
            )
        ).scalars()
    )
    return csv_response(
        "manutencao-preventiva.csv",
        [
            "id",
            "asset_id",
            "assigned_membership_id",
            "maintenance_type",
            "frequency_days",
            "next_due_at",
            "last_completed_at",
            "is_overdue",
            "is_active",
            "instructions",
        ],
        [
            [
                item.id,
                item.asset_id,
                item.assigned_membership_id or "",
                item.maintenance_type,
                item.frequency_days,
                item.next_due_at,
                item.last_completed_at or "",
                item.is_active and item.next_due_at < now,
                item.is_active,
                item.instructions or "",
            ]
            for item in rows
        ],
    )
