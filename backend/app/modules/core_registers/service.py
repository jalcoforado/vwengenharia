from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.base import Base
from app.models.operations import Asset, AssetType, Client, Development, Station
from app.modules.auth.dependencies import AuthContext


async def tenant_get_or_404[ModelT: Base](
    session: AsyncSession,
    model: type[ModelT],
    tenant_id: UUID,
    object_id: UUID,
) -> ModelT:
    obj = (
        await session.execute(
            select(model).where(model.id == object_id, model.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return obj


def add_audit(
    session: AsyncSession,
    context: AuthContext,
    *,
    action: str,
    entity_type: str,
    entity_id: UUID,
    fields: list[str] | None = None,
) -> None:
    session.add(
        AuditEvent(
            tenant_id=context.tenant.id,
            actor_user_id=context.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            event_metadata={"fields": fields or []},
        )
    )


async def list_tenant_objects[ModelT: Base](
    session: AsyncSession,
    model: type[ModelT],
    tenant_id: UUID,
    *filters,
    limit: int = 100,
    offset: int = 0,
) -> list[ModelT]:
    stmt = (
        select(model)
        .where(model.tenant_id == tenant_id, *filters)
        .order_by(model.name)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


async def create_client(session: AsyncSession, context: AuthContext, payload) -> Client:
    client = Client(tenant_id=context.tenant.id, **payload.model_dump())
    session.add(client)
    await session.flush()
    add_audit(session, context, action="CLIENT_CREATE", entity_type="client", entity_id=client.id)
    await session.commit()
    await session.refresh(client)
    return client


async def create_development(session: AsyncSession, context: AuthContext, payload) -> Development:
    await tenant_get_or_404(session, Client, context.tenant.id, payload.client_id)
    development = Development(tenant_id=context.tenant.id, **payload.model_dump())
    session.add(development)
    await session.flush()
    add_audit(
        session,
        context,
        action="DEVELOPMENT_CREATE",
        entity_type="development",
        entity_id=development.id,
    )
    await session.commit()
    await session.refresh(development)
    return development


async def create_station(session: AsyncSession, context: AuthContext, payload) -> Station:
    await tenant_get_or_404(session, Development, context.tenant.id, payload.development_id)
    station = Station(tenant_id=context.tenant.id, **payload.model_dump())
    session.add(station)
    await session.flush()
    add_audit(
        session, context, action="STATION_CREATE", entity_type="station", entity_id=station.id
    )
    await session.commit()
    await session.refresh(station)
    return station


async def create_asset_type(session: AsyncSession, context: AuthContext, payload) -> AssetType:
    asset_type = AssetType(tenant_id=context.tenant.id, **payload.model_dump())
    session.add(asset_type)
    await session.flush()
    add_audit(
        session,
        context,
        action="ASSET_TYPE_CREATE",
        entity_type="asset_type",
        entity_id=asset_type.id,
    )
    await session.commit()
    await session.refresh(asset_type)
    return asset_type


async def create_asset(session: AsyncSession, context: AuthContext, payload) -> Asset:
    await tenant_get_or_404(session, Station, context.tenant.id, payload.station_id)
    await tenant_get_or_404(session, AssetType, context.tenant.id, payload.asset_type_id)
    data = payload.model_dump()
    data["status"] = payload.status.value
    asset = Asset(tenant_id=context.tenant.id, **data)
    session.add(asset)
    await session.flush()
    add_audit(session, context, action="ASSET_CREATE", entity_type="asset", entity_id=asset.id)
    await session.commit()
    await session.refresh(asset)
    return asset


async def update_object[ModelT: Base](
    session: AsyncSession,
    context: AuthContext,
    obj: ModelT,
    payload: BaseModel,
    *,
    action: str,
    entity_type: str,
) -> ModelT:
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        add_audit(
            session,
            context,
            action=action,
            entity_type=entity_type,
            entity_id=obj.id,
            fields=sorted(changes),
        )
        await session.commit()
        await session.refresh(obj)
    return obj


async def validate_update_parents(
    session: AsyncSession,
    context: AuthContext,
    payload: BaseModel,
) -> None:
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("client_id") is not None:
        await tenant_get_or_404(session, Client, context.tenant.id, changes["client_id"])
    if changes.get("development_id") is not None:
        await tenant_get_or_404(
            session, Development, context.tenant.id, changes["development_id"]
        )
    if changes.get("station_id") is not None:
        await tenant_get_or_404(session, Station, context.tenant.id, changes["station_id"])
    if changes.get("asset_type_id") is not None:
        await tenant_get_or_404(session, AssetType, context.tenant.id, changes["asset_type_id"])
