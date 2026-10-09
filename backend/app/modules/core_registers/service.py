from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.base import Base
from app.models.identity import Role
from app.models.operations import (
    Asset,
    AssetType,
    Client,
    ClientDevelopmentContact,
    ContactScope,
    Development,
    Station,
)
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


async def ensure_client_document_is_unique(
    session: AsyncSession,
    tenant_id: UUID,
    document: str | None,
    *,
    ignore_id: UUID | None = None,
) -> None:
    if not document:
        return
    stmt = select(Client.id).where(Client.tenant_id == tenant_id, Client.document == document)
    if ignore_id is not None:
        stmt = stmt.where(Client.id != ignore_id)
    if (await session.execute(stmt)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="client_document_already_exists",
        )


async def create_client(session: AsyncSession, context: AuthContext, payload) -> Client:
    await ensure_client_document_is_unique(session, context.tenant.id, payload.document)
    client = Client(tenant_id=context.tenant.id, **payload.model_dump())
    session.add(client)
    await session.flush()
    add_audit(session, context, action="CLIENT_CREATE", entity_type="client", entity_id=client.id)
    await session.commit()
    await session.refresh(client)
    return client


async def list_client_contacts(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    client_id: UUID | None = None,
    development_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ClientDevelopmentContact]:
    stmt = select(ClientDevelopmentContact).where(
        ClientDevelopmentContact.tenant_id == tenant_id
    )
    if client_id is not None:
        stmt = stmt.where(ClientDevelopmentContact.client_id == client_id)
    if development_id is not None:
        stmt = stmt.where(ClientDevelopmentContact.development_id == development_id)
    stmt = (
        stmt.order_by(ClientDevelopmentContact.created_at, ClientDevelopmentContact.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


PORTAL_ADMIN_ROLES = {Role.SUPERADMIN.value, Role.ADMIN.value}


def _require_portal_admin(context: AuthContext) -> None:
    if context.membership.role not in PORTAL_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="portal_access_requires_admin",
        )


async def set_primary_contact(
    session: AsyncSession,
    development: Development,
    client_id: UUID,
) -> None:
    """Mantem uma unica responsabilidade principal, igual a developments.client_id."""
    rows = list(
        (
            await session.execute(
                select(ClientDevelopmentContact).where(
                    ClientDevelopmentContact.tenant_id == development.tenant_id,
                    ClientDevelopmentContact.development_id == development.id,
                )
            )
        ).scalars()
    )
    for row in rows:
        if row.is_primary and row.client_id != client_id:
            # O antigo principal segue como responsavel, mas sem visao no portal.
            row.is_primary = False
            row.portal_access = False
    # Libera o indice de principal unico antes de promover o novo.
    await session.flush()

    current = next((row for row in rows if row.is_primary and row.client_id == client_id), None)
    if current is not None:
        return
    general = next(
        (
            row
            for row in rows
            if row.client_id == client_id and row.scope == ContactScope.GERAL.value
        ),
        None,
    )
    if general is None:
        session.add(
            ClientDevelopmentContact(
                tenant_id=development.tenant_id,
                client_id=client_id,
                development_id=development.id,
                scope=ContactScope.GERAL.value,
                is_primary=True,
            )
        )
    else:
        general.is_primary = True
        general.is_active = True
    await session.flush()


async def ensure_development_document_is_unique(
    session: AsyncSession,
    tenant_id: UUID,
    document: str | None,
    *,
    ignore_id: UUID | None = None,
) -> None:
    if not document:
        return
    stmt = select(Development.id).where(
        Development.tenant_id == tenant_id, Development.document == document
    )
    if ignore_id is not None:
        stmt = stmt.where(Development.id != ignore_id)
    if (await session.execute(stmt)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="development_document_already_exists",
        )


async def update_development(
    session: AsyncSession,
    context: AuthContext,
    development: Development,
    payload: BaseModel,
) -> Development:
    changes = payload.model_dump(exclude_unset=True)
    await ensure_development_document_is_unique(
        session, context.tenant.id, changes.get("document"), ignore_id=development.id
    )
    new_client_id = changes.get("client_id")
    if new_client_id is not None and new_client_id != development.client_id:
        await set_primary_contact(session, development, new_client_id)
    return await update_object(
        session,
        context,
        development,
        payload,
        action="DEVELOPMENT_UPDATE",
        entity_type="development",
    )


async def _ensure_client_contact_is_unique(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    client_id: UUID,
    development_id: UUID,
    scope: str,
    ignore_id: UUID | None = None,
) -> None:
    stmt = select(ClientDevelopmentContact.id).where(
        ClientDevelopmentContact.tenant_id == tenant_id,
        ClientDevelopmentContact.client_id == client_id,
        ClientDevelopmentContact.development_id == development_id,
        ClientDevelopmentContact.scope == scope,
    )
    if ignore_id is not None:
        stmt = stmt.where(ClientDevelopmentContact.id != ignore_id)
    if (await session.execute(stmt)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="client_contact_already_exists",
        )


async def create_client_contact(
    session: AsyncSession, context: AuthContext, payload
) -> ClientDevelopmentContact:
    await tenant_get_or_404(session, Client, context.tenant.id, payload.client_id)
    await tenant_get_or_404(session, Development, context.tenant.id, payload.development_id)
    await _ensure_client_contact_is_unique(
        session,
        context.tenant.id,
        client_id=payload.client_id,
        development_id=payload.development_id,
        scope=payload.scope.value,
    )
    if payload.portal_access:
        _require_portal_admin(context)
    contact = ClientDevelopmentContact(
        tenant_id=context.tenant.id,
        client_id=payload.client_id,
        development_id=payload.development_id,
        scope=payload.scope.value,
        portal_access=payload.portal_access,
    )
    session.add(contact)
    await session.flush()
    add_audit(
        session,
        context,
        action="CLIENT_CONTACT_CREATE",
        entity_type="client_development_contact",
        entity_id=contact.id,
    )
    await session.commit()
    await session.refresh(contact)
    return contact


async def update_client_contact(
    session: AsyncSession,
    context: AuthContext,
    contact: ClientDevelopmentContact,
    payload: BaseModel,
) -> ClientDevelopmentContact:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if changes.get("is_active") is False:
        if contact.is_primary:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="primary_contact_cannot_be_deactivated",
            )
        # Quem deixa de responder pelo empreendimento perde a visao no portal.
        changes["portal_access"] = False
    if changes.get("portal_access") is True and not contact.portal_access:
        # Revogar e livre para quem cadastra; conceder exige administrador.
        _require_portal_admin(context)
    if "scope" in changes:
        changes["scope"] = changes["scope"].value
        await _ensure_client_contact_is_unique(
            session,
            context.tenant.id,
            client_id=contact.client_id,
            development_id=contact.development_id,
            scope=changes["scope"],
            ignore_id=contact.id,
        )
    for field, value in changes.items():
        setattr(contact, field, value)
    if changes:
        add_audit(
            session,
            context,
            action="CLIENT_CONTACT_UPDATE",
            entity_type="client_development_contact",
            entity_id=contact.id,
            fields=sorted(changes),
        )
        await session.commit()
        await session.refresh(contact)
    return contact


async def create_development(session: AsyncSession, context: AuthContext, payload) -> Development:
    await tenant_get_or_404(session, Client, context.tenant.id, payload.client_id)
    await ensure_development_document_is_unique(
        session, context.tenant.id, payload.document
    )
    development = Development(tenant_id=context.tenant.id, **payload.model_dump())
    session.add(development)
    await session.flush()
    await set_primary_contact(session, development, development.client_id)
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
