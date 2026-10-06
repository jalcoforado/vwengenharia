from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.identity import Role
from app.models.integration import IntegrationCredential
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.integration.dependencies import (
    IntegrationContext,
    get_integration_context,
)
from app.modules.integration.schemas import (
    IntegrationEnvelope,
    IntegrationKeyCreate,
    IntegrationKeyCreated,
    IntegrationKeyRead,
    IntegrationResource,
)
from app.modules.integration.service import (
    create_integration_key,
    export_resource,
    list_integration_keys,
    revoke_integration_key,
)

router = APIRouter(tags=["integracao"])

ADMIN_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
)
AdminContextDep = Annotated[AuthContext, Depends(require_roles(*ADMIN_ROLES))]
IntegrationContextDep = Annotated[
    IntegrationContext,
    Depends(get_integration_context),
]
ExportLimit = Annotated[int, Query(ge=1, le=1000)]
ExportOffset = Annotated[int, Query(ge=0)]


def key_read(credential: IntegrationCredential) -> IntegrationKeyRead:
    return IntegrationKeyRead(
        id=credential.id,
        name=credential.name,
        key_prefix=credential.key_prefix,
        created_at=credential.created_at,
        last_used_at=credential.last_used_at,
        revoked_at=credential.revoked_at,
    )


@router.get("/integration-keys", response_model=list[IntegrationKeyRead])
async def get_integration_keys(
    context: AdminContextDep,
    session: SessionDep,
) -> list[IntegrationKeyRead]:
    keys = await list_integration_keys(session, context)
    return [key_read(item) for item in keys]


@router.post(
    "/integration-keys",
    response_model=IntegrationKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def post_integration_key(
    payload: IntegrationKeyCreate,
    context: AdminContextDep,
    session: SessionDep,
) -> IntegrationKeyCreated:
    credential, secret = await create_integration_key(session, context, payload)
    base = key_read(credential)
    return IntegrationKeyCreated(**base.model_dump(), secret=secret)


@router.post(
    "/integration-keys/{credential_id}/revoke",
    response_model=IntegrationKeyRead,
)
async def post_revoke_integration_key(
    credential_id: UUID,
    context: AdminContextDep,
    session: SessionDep,
) -> IntegrationKeyRead:
    credential = await revoke_integration_key(
        session,
        context,
        credential_id,
    )
    return key_read(credential)


@router.get(
    "/integration/v1/{resource}",
    response_model=IntegrationEnvelope,
)
async def get_integration_resource(
    resource: IntegrationResource,
    context: IntegrationContextDep,
    session: SessionDep,
    updated_since: datetime | None = None,
    snapshot_at: datetime | None = None,
    limit: ExportLimit = 500,
    offset: ExportOffset = 0,
) -> IntegrationEnvelope:
    data = await export_resource(
        session,
        context,
        resource,
        updated_since=updated_since,
        snapshot_at=snapshot_at,
        limit=limit,
        offset=offset,
    )
    return IntegrationEnvelope.model_validate(data)
