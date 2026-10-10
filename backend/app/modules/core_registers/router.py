from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.identity import Role
from app.models.operations import (
    Asset,
    AssetType,
    Client,
    ClientDevelopmentContact,
    ContractingParty,
    Development,
    ProcessUnit,
    ProcessUnitType,
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
    ContractingPartyCreate,
    ContractingPartyRead,
    ContractingPartyUpdate,
    DevelopmentCreate,
    DevelopmentRead,
    DevelopmentUpdate,
    FacadePhotoComplete,
    FacadePhotoPresign,
    FacadePhotoUpload,
    FacadePhotoUrl,
    ProcessUnitCreate,
    ProcessUnitRead,
    ProcessUnitTypeCreate,
    ProcessUnitTypeRead,
    ProcessUnitTypeUpdate,
    ProcessUnitUpdate,
    StationCreate,
    StationRead,
    StationUpdate,
)
from app.modules.core_registers.service import (
    complete_facade_photo,
    create_asset,
    create_asset_type,
    create_client,
    create_client_contact,
    create_contracting_party,
    create_development,
    create_process_unit,
    create_process_unit_type,
    create_station,
    ensure_client_document_is_unique,
    facade_photo_url,
    list_client_contacts,
    list_tenant_objects,
    presign_facade_photo,
    remove_facade_photo,
    tenant_get_or_404,
    update_asset,
    update_client_contact,
    update_contracting_party,
    update_development,
    update_object,
    update_process_unit,
    update_process_unit_type,
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
    await ensure_client_document_is_unique(
        session, context.tenant.id, payload.document, ignore_id=client.id
    )
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


@router.get("/contracting-parties", response_model=list[ContractingPartyRead])
async def list_contracting_parties(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
) -> list[ContractingParty]:
    return await list_tenant_objects(
        session, ContractingParty, context.tenant.id, limit=limit, offset=offset
    )


@router.post(
    "/contracting-parties",
    response_model=ContractingPartyRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_contracting_party(
    payload: ContractingPartyCreate, context: WriteContextDep, session: SessionDep
) -> ContractingParty:
    return await create_contracting_party(session, context, payload)


@router.patch("/contracting-parties/{party_id}", response_model=ContractingPartyRead)
async def patch_contracting_party(
    party_id: UUID,
    payload: ContractingPartyUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> ContractingParty:
    party = await tenant_get_or_404(session, ContractingParty, context.tenant.id, party_id)
    return await update_contracting_party(session, context, party, payload)


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
    return await update_development(session, context, development, payload)


@router.post(
    "/developments/{development_id}/facade-photo/presign", response_model=FacadePhotoUpload
)
async def presign_development_facade_photo(
    development_id: UUID,
    payload: FacadePhotoPresign,
    context: WriteContextDep,
    session: SessionDep,
) -> dict:
    development = await tenant_get_or_404(
        session, Development, context.tenant.id, development_id
    )
    return presign_facade_photo(development, payload)


@router.post(
    "/developments/{development_id}/facade-photo/complete", response_model=DevelopmentRead
)
async def complete_development_facade_photo(
    development_id: UUID,
    payload: FacadePhotoComplete,
    context: WriteContextDep,
    session: SessionDep,
) -> Development:
    development = await tenant_get_or_404(
        session, Development, context.tenant.id, development_id
    )
    return await complete_facade_photo(session, context, development, payload.object_key)


@router.get("/developments/{development_id}/facade-photo", response_model=FacadePhotoUrl)
async def get_development_facade_photo(
    development_id: UUID, context: ReadContextDep, session: SessionDep
) -> dict:
    development = await tenant_get_or_404(
        session, Development, context.tenant.id, development_id
    )
    return facade_photo_url(development)


@router.delete("/developments/{development_id}/facade-photo", response_model=DevelopmentRead)
async def delete_development_facade_photo(
    development_id: UUID, context: WriteContextDep, session: SessionDep
) -> Development:
    development = await tenant_get_or_404(
        session, Development, context.tenant.id, development_id
    )
    return await remove_facade_photo(session, context, development)


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


@router.get("/process-unit-types", response_model=list[ProcessUnitTypeRead])
async def list_process_unit_types(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
) -> list[ProcessUnitType]:
    return await list_tenant_objects(
        session, ProcessUnitType, context.tenant.id, limit=limit, offset=offset
    )


@router.post(
    "/process-unit-types",
    response_model=ProcessUnitTypeRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_process_unit_type(
    payload: ProcessUnitTypeCreate, context: WriteContextDep, session: SessionDep
) -> ProcessUnitType:
    return await create_process_unit_type(session, context, payload)


@router.patch("/process-unit-types/{unit_type_id}", response_model=ProcessUnitTypeRead)
async def patch_process_unit_type(
    unit_type_id: UUID,
    payload: ProcessUnitTypeUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> ProcessUnitType:
    unit_type = await tenant_get_or_404(
        session, ProcessUnitType, context.tenant.id, unit_type_id
    )
    return await update_process_unit_type(session, context, unit_type, payload)


@router.get("/process-units", response_model=list[ProcessUnitRead])
async def list_process_units(
    context: ReadContextDep,
    session: SessionDep,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    station_id: UUID | None = None,
) -> list[ProcessUnit]:
    filters = [] if station_id is None else [ProcessUnit.station_id == station_id]
    return await list_tenant_objects(
        session, ProcessUnit, context.tenant.id, *filters, limit=limit, offset=offset
    )


@router.post(
    "/process-units", response_model=ProcessUnitRead, status_code=status.HTTP_201_CREATED
)
async def post_process_unit(
    payload: ProcessUnitCreate, context: WriteContextDep, session: SessionDep
) -> ProcessUnit:
    return await create_process_unit(session, context, payload)


@router.patch("/process-units/{unit_id}", response_model=ProcessUnitRead)
async def patch_process_unit(
    unit_id: UUID,
    payload: ProcessUnitUpdate,
    context: WriteContextDep,
    session: SessionDep,
) -> ProcessUnit:
    unit = await tenant_get_or_404(session, ProcessUnit, context.tenant.id, unit_id)
    return await update_process_unit(session, context, unit, payload)


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
    return await update_asset(session, context, asset, payload)
