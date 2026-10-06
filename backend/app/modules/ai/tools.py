from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import Measurement, Visit
from app.models.maintenance import Occurrence, OccurrenceStatus, WorkOrder, WorkOrderStatus
from app.models.operations import Asset, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import tenant_get_or_404
from app.modules.operations.service import dashboard_overview


TOOL_DEFINITIONS = [
    {
        "name": "operational_overview",
        "description": "Retorna indicadores consolidados da operacao do tenant atual.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "list_open_work_orders",
        "description": "Lista ordens de servico abertas, com prioridade, status, SLA e estacao.",
        "input_schema": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": "string",
                    "enum": ["BAIXA", "MEDIA", "ALTA", "CRITICA"],
                },
                "overdue_only": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "list_open_occurrences",
        "description": "Lista ocorrencias ainda nao resolvidas no tenant atual.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["BAIXA", "MEDIA", "ALTA", "CRITICA"],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "search_stations",
        "description": "Busca estacoes pelo nome ou codigo dentro do tenant atual.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 120},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "station_snapshot",
        "description": (
            "Retorna um retrato operacional de uma estacao: ativos, visitas recentes, "
            "medicoes, ocorrencias e OS abertas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "station_id": {"type": "string", "format": "uuid"},
            },
            "required": ["station_id"],
            "additionalProperties": False,
        },
    },
]


def _dt(value):
    return value.isoformat() if value is not None else None


async def execute_tool(
    session: AsyncSession,
    context: AuthContext,
    name: str,
    arguments: dict,
):
    if name == "operational_overview":
        return await dashboard_overview(session, context)

    if name == "list_open_work_orders":
        limit = min(max(int(arguments.get("limit", 10)), 1), 20)
        stmt = (
            select(WorkOrder, Station)
            .join(Station, Station.id == WorkOrder.station_id)
            .where(
                WorkOrder.tenant_id == context.tenant.id,
                Station.tenant_id == context.tenant.id,
                WorkOrder.status.notin_(
                    [WorkOrderStatus.VALIDADA.value, WorkOrderStatus.CANCELADA.value]
                ),
            )
        )
        priority = arguments.get("priority")
        if priority:
            stmt = stmt.where(WorkOrder.priority == priority)
        if arguments.get("overdue_only"):
            stmt = stmt.where(WorkOrder.sla_due_at < datetime.now(UTC))
        rows = (
            await session.execute(
                stmt.order_by(WorkOrder.sla_due_at).limit(limit)
            )
        ).all()
        return [
            {
                "id": str(order.id),
                "station_id": str(order.station_id),
                "station": station.name,
                "priority": order.priority,
                "status": order.status,
                "description": order.description,
                "sla_due_at": _dt(order.sla_due_at),
                "overdue": order.sla_due_at < datetime.now(UTC),
            }
            for order, station in rows
        ]

    if name == "list_open_occurrences":
        limit = min(max(int(arguments.get("limit", 10)), 1), 20)
        stmt = (
            select(Occurrence, Station)
            .join(Station, Station.id == Occurrence.station_id)
            .where(
                Occurrence.tenant_id == context.tenant.id,
                Station.tenant_id == context.tenant.id,
                Occurrence.status.notin_(
                    [OccurrenceStatus.RESOLVIDA.value, OccurrenceStatus.CANCELADA.value]
                ),
            )
        )
        severity = arguments.get("severity")
        if severity:
            stmt = stmt.where(Occurrence.severity == severity)
        rows = (
            await session.execute(
                stmt.order_by(desc(Occurrence.detected_at)).limit(limit)
            )
        ).all()
        return [
            {
                "id": str(item.id),
                "station_id": str(item.station_id),
                "station": station.name,
                "type": item.occurrence_type,
                "severity": item.severity,
                "status": item.status,
                "description": item.description,
                "detected_at": _dt(item.detected_at),
            }
            for item, station in rows
        ]

    if name == "search_stations":
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="station_search_query_required",
            )
        limit = min(max(int(arguments.get("limit", 8)), 1), 10)
        pattern = f"%{query}%"
        rows = list(
            (
                await session.execute(
                    select(Station)
                    .where(
                        Station.tenant_id == context.tenant.id,
                        (Station.name.ilike(pattern) | Station.code.ilike(pattern)),
                    )
                    .order_by(Station.name)
                    .limit(limit)
                )
            ).scalars()
        )
        return [
            {
                "id": str(station.id),
                "name": station.name,
                "code": station.code,
                "station_type": station.station_type,
                "is_active": station.is_active,
            }
            for station in rows
        ]

    if name == "station_snapshot":
        try:
            station_id = UUID(str(arguments["station_id"]))
        except (KeyError, TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid_station_id",
            ) from None

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
                        Asset.is_active.is_(True),
                    )
                    .order_by(Asset.name)
                )
            ).scalars()
        )
        visits = list(
            (
                await session.execute(
                    select(Visit)
                    .where(
                        Visit.tenant_id == context.tenant.id,
                        Visit.station_id == station.id,
                    )
                    .order_by(desc(Visit.scheduled_for))
                    .limit(5)
                )
            ).scalars()
        )
        visit_ids = [visit.id for visit in visits]
        measurements = []
        if visit_ids:
            measurements = list(
                (
                    await session.execute(
                        select(Measurement)
                        .where(
                            Measurement.tenant_id == context.tenant.id,
                            Measurement.visit_id.in_(visit_ids),
                        )
                        .order_by(desc(Measurement.measured_at))
                        .limit(12)
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
                        Occurrence.status.notin_(
                            [
                                OccurrenceStatus.RESOLVIDA.value,
                                OccurrenceStatus.CANCELADA.value,
                            ]
                        ),
                    )
                    .order_by(desc(Occurrence.detected_at))
                    .limit(10)
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
                        WorkOrder.status.notin_(
                            [
                                WorkOrderStatus.VALIDADA.value,
                                WorkOrderStatus.CANCELADA.value,
                            ]
                        ),
                    )
                    .order_by(WorkOrder.sla_due_at)
                    .limit(10)
                )
            ).scalars()
        )
        return {
            "station": {
                "id": str(station.id),
                "name": station.name,
                "code": station.code,
                "station_type": station.station_type,
                "is_active": station.is_active,
            },
            "assets": [
                {
                    "id": str(asset.id),
                    "name": asset.name,
                    "status": asset.status,
                    "manufacturer": asset.manufacturer,
                    "model": asset.model,
                }
                for asset in assets
            ],
            "recent_visits": [
                {
                    "id": str(visit.id),
                    "scheduled_for": _dt(visit.scheduled_for),
                    "status": visit.status,
                    "finished_at": _dt(visit.finished_at),
                }
                for visit in visits
            ],
            "recent_measurements": [
                {
                    "type": item.measurement_type,
                    "status": item.status,
                    "value": float(item.value) if item.value is not None else None,
                    "unit": item.unit,
                    "reason": item.reason,
                    "measured_at": _dt(item.measured_at),
                }
                for item in measurements
            ],
            "open_occurrences": [
                {
                    "id": str(item.id),
                    "type": item.occurrence_type,
                    "severity": item.severity,
                    "description": item.description,
                    "detected_at": _dt(item.detected_at),
                }
                for item in occurrences
            ],
            "open_work_orders": [
                {
                    "id": str(item.id),
                    "priority": item.priority,
                    "status": item.status,
                    "description": item.description,
                    "sla_due_at": _dt(item.sla_due_at),
                }
                for item in work_orders
            ],
        }

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="unknown_ai_tool",
    )


def result_count(value) -> int | None:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return None
