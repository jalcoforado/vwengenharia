import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Header, HTTPException, status
from sqlalchemy import select

from app.models.identity import Tenant
from app.models.integration import IntegrationCredential
from app.modules.auth.dependencies import SessionDep


@dataclass(slots=True)
class IntegrationContext:
    tenant_id: UUID
    credential_id: UUID


async def get_integration_context(
    session: SessionDep,
    integration_key: Annotated[str | None, Header(alias="X-Integration-Key")] = None,
) -> IntegrationContext:
    if not integration_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_integration_key",
        )

    key_hash = hashlib.sha256(integration_key.encode("utf-8")).hexdigest()
    stmt = (
        select(IntegrationCredential, Tenant)
        .join(Tenant, Tenant.id == IntegrationCredential.tenant_id)
        .where(
            IntegrationCredential.key_hash == key_hash,
            IntegrationCredential.revoked_at.is_(None),
            Tenant.is_active.is_(True),
        )
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_integration_key",
        )

    credential, tenant = row
    credential.last_used_at = datetime.now(UTC)
    await session.commit()

    return IntegrationContext(
        tenant_id=tenant.id,
        credential_id=credential.id,
    )
