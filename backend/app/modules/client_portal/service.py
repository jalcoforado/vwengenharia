from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import Visit
from app.models.identity import Membership, Role
from app.models.maintenance import Occurrence, WorkOrder
from app.models.operations import Client, ClientMembershipAccess, Development, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit


async def build_client_portal(
    session: AsyncSession,
    context: AuthContext,
) -> dict:
    client_ids = list(
        (
            await session.execute(
                select(ClientMembershipAccess.client_id).where(
                    ClientMembershipAccess.tenant_id == context.tenant.id,
                    ClientMembershipAccess.membership_id == context.membership.id,
                )
            )
        ).scalars()
    )
    if not client_ids:
        return {
            "clients": [],
            "stations": [],
            "visits": [],
            "occurrences": [],
            "work_orders": [],
        }

    clients = list(
        (
            await session.execute(
                select(Client).where(
                    Client.tenant_id == context.tenant.id,
                    Client.id.in_(client_ids),
                )
            )
        ).scalars()
    )
    development_rows = list(
        (
            await session.execute(
                select(Development).where(
                    Development.tenant_id == context.tenant.id,
                    Development.client_id.in_(client_ids),
                )
            )
        ).scalars()
    )
    development_ids = [item.id for item in development_rows]
    development_map = {item.id: item for item in development_rows}
    stations = (
        list(
            (
                await session.execute(
                    select(Station).where(
                        Station.tenant_id == context.tenant.id,
                        Station.development_id.in_(development_ids),
                    )
                )
            ).scalars()
        )
        if development_ids
        else []
    )
    station_ids = [item.id for item in stations]

    visits = (
        list(
            (
                await session.execute(
                    select(Visit)
                    .where(
                        Visit.tenant_id == context.tenant.id,
                        Visit.station_id.in_(station_ids),
                    )
                    .order_by(Visit.scheduled_for.desc())
                    .limit(200)
                )
            ).scalars()
        )
        if station_ids
        else []
    )
    occurrences = (
        list(
            (
                await session.execute(
                    select(Occurrence)
                    .where(
                        Occurrence.tenant_id == context.tenant.id,
                        Occurrence.station_id.in_(station_ids),
                    )
                    .order_by(Occurrence.detected_at.desc())
                    .limit(200)
                )
            ).scalars()
        )
        if station_ids
        else []
    )
    work_orders = (
        list(
            (
                await session.execute(
                    select(WorkOrder)
                    .where(
                        WorkOrder.tenant_id == context.tenant.id,
                        WorkOrder.station_id.in_(station_ids),
                    )
                    .order_by(WorkOrder.created_at.desc())
                    .limit(200)
                )
            ).scalars()
        )
        if station_ids
        else []
    )

    return {
        "clients": [{"id": item.id, "name": item.name} for item in clients],
        "stations": [
            {
                "id": item.id,
                "development_id": item.development_id,
                "development_name": development_map[item.development_id].name,
                "name": item.name,
                "code": item.code,
                "station_type": item.station_type,
            }
            for item in stations
        ],
        "visits": [
            {
                "id": item.id,
                "station_id": item.station_id,
                "scheduled_for": item.scheduled_for,
                "finished_at": item.finished_at,
                "status": item.status,
            }
            for item in visits
        ],
        "occurrences": [
            {
                "id": item.id,
                "station_id": item.station_id,
                "occurrence_type": item.occurrence_type,
                "severity": item.severity,
                "status": item.status,
                "description": item.description,
                "detected_at": item.detected_at,
            }
            for item in occurrences
        ],
        "work_orders": [
            {
                "id": item.id,
                "station_id": item.station_id,
                "asset_id": item.asset_id,
                "priority": item.priority,
                "status": item.status,
                "description": item.description,
                "sla_due_at": item.sla_due_at,
                "completed_at": item.completed_at,
            }
            for item in work_orders
        ],
    }



async def grant_client_access(
    session: AsyncSession,
    context: AuthContext,
    *,
    membership_id,
    client_id,
):
    membership = (
        await session.execute(
            select(Membership).where(
                Membership.id == membership_id,
                Membership.tenant_id == context.tenant.id,
                Membership.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="membership_not_found")
    if membership.role != Role.CLIENTE.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="membership_is_not_client_role",
        )

    client = (
        await session.execute(
            select(Client).where(
                Client.id == client_id,
                Client.tenant_id == context.tenant.id,
                Client.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client_not_found")

    existing = (
        await session.execute(
            select(ClientMembershipAccess).where(
                ClientMembershipAccess.tenant_id == context.tenant.id,
                ClientMembershipAccess.membership_id == membership.id,
                ClientMembershipAccess.client_id == client.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    access = ClientMembershipAccess(
        tenant_id=context.tenant.id,
        membership_id=membership.id,
        client_id=client.id,
    )
    session.add(access)
    await session.flush()
    add_audit(
        session,
        context,
        action="CLIENT_PORTAL_ACCESS_GRANT",
        entity_type="client_membership_access",
        entity_id=access.id,
        fields=["membership_id", "client_id"],
    )
    await session.commit()
    await session.refresh(access)
    return access


async def list_client_access(
    session: AsyncSession,
    context: AuthContext,
):
    stmt = (
        select(ClientMembershipAccess)
        .where(ClientMembershipAccess.tenant_id == context.tenant.id)
        .order_by(ClientMembershipAccess.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars())
