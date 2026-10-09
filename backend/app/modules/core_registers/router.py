from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.identity import Role
from app.models.operations import (
    Asset,
    AssetType,
    Client,
    ClientDevelopmentContact,
    Development,
    Station,
)
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.core_registers.schemas import (
    AssetCreate,
    AssetRead,
    AssetTypeCreate,
    AssetTypeRead,
    AssetTypeUpdate,
    AssetUpdate,
    ClientContactCreate,
    ClientContactRead,
    ClientContactUpdate,
    ClientCreate,
    ClientRead,
    ClientUpdate,
    DevelopmentCreate,
    DevelopmentRead,
    DevelopmentUpdate,
    StationCreate,
    StationRead,
    StationUpdate,
)
from app.modules.core_registers.service import (
    create_asset,
    create_asset_type,
    create_client,
    create_client_contact,
    create_development,
    create_station,
    list_client_contacts,
    list_tenant_objects,
    tenant_get_or_404,
    update_client_contact,
    update_object,
    validate_update_parents,
)

router = APIRouter(tags=["cadastros"])

INTERNAL_READ_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
    Role.TECNICO.value,
    Role.MANUTENCAO.value,
)
WRITE_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
)
ReadContextDep = Annotated[AuthContext, Depends(require_roles(*INTERNAL_READ_ROLES))]
WriteContextDep = Annotated[AuthContext, Depends(require_roles(*WRITE_ROLES))]
PageLimit = Annotated[int, Query(ge=1, le=500)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("/clients", response_model=list[ClientRead])
async def list_clients(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
) -> list[Client]:
    return await list_tenant_objects(
        session, Client, context.tenant.id, limit=limit, offset=offset
    )


@router.post("/clients", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def post_client(
    payload: ClientCreate, context: WriteContextDep, session: SessionDep
) -> Client:
    return await create_client(session, context, payload)


@router.get("/clients/{client_id}", response_model=ClientRead)
async def get_client(client_id: UUID, context: ReadContextDep, session: SessionDep) -> Client:
    return await tenant_get_or_404(session, Client, context.tenant.id, client_id)


@router.patch("/clients/{client_id}", response_model=ClientRead)
async def patch_client(
    client_id: UUID,
    payload: ClientUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> Client:
    client = await tenant_get_or_404(session, Client, context.tenant.id, client_id)
    return await update_object(
        session,
        context,
        client,
        payload,
        action="CLIENT_UPDATE",
        entity_type="client",
    )


@router.get("/client-contacts", response_model=list[ClientContactRead])
async def get_client_contacts(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    client_id: UUID | None = None,
    development_id: UUID | None = None,
) -> list[ClientDevelopmentContact]:
    return await list_client_contacts(
        session,
        context.tenant.id,
        client_id=client_id,
        development_id=development_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/client-contacts",
    response_model=ClientContactRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_client_contact(
    payload: ClientContactCreate, context: WriteContextDep, session: SessionDep
) -> ClientDevelopmentContact:
    return await create_client_contact(session, context, payload)


@router.patch("/client-contacts/{contact_id}", response_model=ClientContactRead)
async def patch_client_contact(
    contact_id: UUID,
    payload: ClientContactUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> ClientDevelopmentContact:
    contact = await tenant_get_or_404(
        session, ClientDevelopmentContact, context.tenant.id, contact_id
    )
    return await update_client_contact(session, context, contact, payload)


@router.get("/developments", response_model=list[DevelopmentRead])
async def list_developments(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    client_id: UUID | None = None,
) -> list[Development]:
    filters = [] if client_id is None else [Development.client_id == client_id]
    return await list_tenant_objects(
        session, Development, context.tenant.id, *filters, limit=limit, offset=offset
    )


@router.post(
    "/developments", response_model=DevelopmentRead, status_code=status.HTTP_201_CREATED
)
async def post_development(
    payload: DevelopmentCreate, context: WriteContextDep, session: SessionDep
) -> Development:
    return await create_development(session, context, payload)


@router.get("/developments/{development_id}", response_model=DevelopmentRead)
async def get_development(
    development_id: UUID, context: ReadContextDep, session: SessionDep
) -> Development:
    return await tenant_get_or_404(
        session, Development, context.tenant.id, development_id
    )


@router.patch("/developments/{development_id}", response_model=DevelopmentRead)
async def patch_development(
    development_id: UUID,
    payload: DevelopmentUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> Development:
    development = await tenant_get_or_404(
        session, Development, context.tenant.id, development_id
    )
    await validate_update_parents(session, context, payload)
    return await update_object(
        session,
        context,
        development,
        payload,
        action="DEVELOPMENT_UPDATE",
        entity_type="development",
    )


@router.get("/stations", response_model=list[StationRead])
async def list_stations(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    development_id: UUID | None = None,
) -> list[Station]:
    filters = [] if development_id is None else [Station.development_id == development_id]
    return await list_tenant_objects(
        session, Station, context.tenant.id, *filters, limit=limit, offset=offset
    )


@router.post("/stations", response_model=StationRead, status_code=status.HTTP_201_CREATED)
async def post_station(
    payload: StationCreate, context: WriteContextDep, session: SessionDep
) -> Station:
    return await create_station(session, context, payload)


@router.get("/stations/{station_id}", response_model=StationRead)
async def get_station(
    station_id: UUID, context: ReadContextDep, session: SessionDep
) -> Station:
    return await tenant_get_or_404(session, Station, context.tenant.id, station_id)


@router.patch("/stations/{station_id}", response_model=StationRead)
async def patch_station(
    station_id: UUID,
    payload: StationUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> Station:
    station = await tenant_get_or_404(session, Station, context.tenant.id, station_id)
    await validate_update_parents(session, context, payload)
    return await update_object(
        session,
        context,
        station,
        payload,
        action="STATION_UPDATE",
        entity_type="station",
    )


@router.get("/asset-types", response_model=list[AssetTypeRead])
async def list_asset_types(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
) -> list[AssetType]:
    return await list_tenant_objects(
        session, AssetType, context.tenant.id, limit=limit, offset=offset
    )


@router.post(
    "/asset-types", response_model=AssetTypeRead, status_code=status.HTTP_201_CREATED
)
async def post_asset_type(
    payload: AssetTypeCreate, context: WriteContextDep, session: SessionDep
) -> AssetType:
    return await create_asset_type(session, context, payload)


@router.patch("/asset-types/{asset_type_id}", response_model=AssetTypeRead)
async def patch_asset_type(
    asset_type_id: UUID,
    payload: AssetTypeUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> AssetType:
    asset_type = await tenant_get_or_404(
        session, AssetType, context.tenant.id, asset_type_id
    )
    return await update_object(
        session,
        context,
        asset_type,
        payload,
        action="ASSET_TYPE_UPDATE",
        entity_type="asset_type",
    )


@router.get("/assets", response_model=list[AssetRead])
async def list_assets(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    station_id: UUID | None = None,
) -> list[Asset]:
    filters = [] if station_id is None else [Asset.station_id == station_id]
    return await list_tenant_objects(
        session, Asset, context.tenant.id, *filters, limit=limit, offset=offset
    )


@router.get("/stations/{station_id}/assets", response_model=list[AssetRead])
async def list_station_assets(
    station_id: UUID,
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
) -> list[Asset]:
    await tenant_get_or_404(session, Station, context.tenant.id, station_id)
    return await list_tenant_objects(
        session,
        Asset,
        context.tenant.id,
        Asset.station_id == station_id,
        limit=limit,
        offset=offset,
    )


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_asset(
    payload: AssetCreate, context: WriteContextDep, session: SessionDep
) -> Asset:
    return await create_asset(session, context, payload)


@router.get("/assets/{asset_id}", response_model=AssetRead)
async def get_asset(asset_id: UUID, context: ReadContextDep, session: SessionDep) -> Asset:
    return await tenant_get_or_404(session, Asset, context.tenant.id, asset_id)


@router.patch("/assets/{asset_id}", response_model=AssetRead)
async def patch_asset(
    asset_id: UUID,
    payload: AssetUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> Asset:
    asset = await tenant_get_or_404(session, Asset, context.tenant.id, asset_id)
    await validate_update_parents(session, context, payload)
    return await update_object(
        session,
        context,
        asset,
        payload,
        action="ASSET_UPDATE",
        entity_type="asset",
    )
