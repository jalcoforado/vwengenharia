from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import Visit
from app.models.maintenance import MaintenancePlan, Occurrence, WorkOrder, WorkOrderStatus
from app.models.materials import MaterialRequest, RequestStatus
from app.models.operations import Asset, AssetStatus, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import tenant_get_or_404


async def station_overview(
    session: AsyncSession,
    context: AuthContext,
    station_id,
) -> dict:
    station = await tenant_get_or_404(
        session, Station, context.tenant.id, station_id
    )

    assets = list(
        (
            await session.execute(
                select(Asset)
                .where(
                    Asset.tenant_id == context.tenant.id,
                    Asset.station_id == station.id,
                )
                .order_by(Asset.name)
            )
        ).scalars()
    )
    asset_ids = [asset.id for asset in assets]

    visits = list(
        (
            await session.execute(
                select(Visit)
                .where(
                    Visit.tenant_id == context.tenant.id,
                    Visit.station_id == station.id,
                )
                .order_by(Visit.scheduled_for.desc())
                .limit(30)
            )
        ).scalars()
    )

    occurrences = list(
        (
            await session.execute(
                select(Occurrence)
                .where(
                    Occurrence.tenant_id == context.tenant.id,
                    Occurrence.station_id == station.id,
                )
                .order_by(Occurrence.detected_at.desc())
                .limit(50)
            )
        ).scalars()
    )

    work_orders = list(
        (
            await session.execute(
                select(WorkOrder)
                .where(
                    WorkOrder.tenant_id == context.tenant.id,
                    WorkOrder.station_id == station.id,
                )
                .order_by(WorkOrder.created_at.desc())
                .limit(50)
            )
        ).scalars()
    )

    if asset_ids:
        maintenance_plans = list(
            (
                await session.execute(
                    select(MaintenancePlan)
                    .where(
                        MaintenancePlan.tenant_id == context.tenant.id,
                        MaintenancePlan.asset_id.in_(asset_ids),
                    )
                    .order_by(MaintenancePlan.next_due_at)
                )
            ).scalars()
        )
    else:
        maintenance_plans = []

    material_requests = list(
        (
            await session.execute(
                select(MaterialRequest)
                .where(
                    MaterialRequest.tenant_id == context.tenant.id,
                    MaterialRequest.station_id == station.id,
                )
                .order_by(MaterialRequest.created_at.desc())
                .limit(50)
            )
        ).scalars()
    )

    now = datetime.now(UTC)
    closed_work_orders = {
        WorkOrderStatus.VALIDADA.value,
        WorkOrderStatus.CANCELADA.value,
    }
    unavailable_statuses = {
        AssetStatus.DESLIGADO.value,
        AssetStatus.EM_MANUTENCAO.value,
        AssetStatus.AGUARDANDO_MANUTENCAO.value,
        AssetStatus.FORA_DA_ESTACAO.value,
        AssetStatus.AGUARDANDO_INSTALACAO.value,
    }

    open_work_orders = [
        item for item in work_orders if item.status not in closed_work_orders
    ]

    return {
        "station": station,
        "summary": {
            "active_assets": sum(1 for item in assets if item.is_active),
            "unavailable_assets": sum(
                1
                for item in assets
                if item.is_active and item.status in unavailable_statuses
            ),
            "open_occurrences": sum(
                1
                for item in occurrences
                if item.status not in {"RESOLVIDA", "CANCELADA"}
            ),
            "open_work_orders": len(open_work_orders),
            "overdue_work_orders": sum(
                1
                for item in open_work_orders
                if item.sla_due_at < now
            ),
            "overdue_maintenance": sum(
                1
                for item in maintenance_plans
                if item.is_active and item.next_due_at < now
            ),
            "open_material_requests": sum(
                1
                for item in material_requests
                if item.status not in {
                    RequestStatus.ATENDIDA.value,
                    RequestStatus.CANCELADA.value,
                }
            ),
        },
        "assets": assets,
        "visits": visits,
        "occurrences": occurrences,
        "work_orders": work_orders,
        "maintenance_plans": maintenance_plans,
        "material_requests": material_requests,
    }
