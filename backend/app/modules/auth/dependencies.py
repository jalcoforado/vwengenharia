from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.identity import Membership, Tenant, User

bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthContext:
    user: User
    membership: Membership
    tenant: Tenant


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
        membership_id = UUID(payload["membership_id"])
        tenant_id = UUID(payload["tenant_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token"
        ) from None

    stmt = (
        select(Membership)
        .options(selectinload(Membership.user), selectinload(Membership.tenant))
        .where(
            Membership.id == membership_id,
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id,
            Membership.is_active.is_(True),
        )
    )
    membership = (await session.execute(stmt)).scalar_one_or_none()
    if (
        membership is None
        or not membership.user.is_active
        or not membership.tenant.is_active
        or membership.role != payload.get("role")
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_context")

    return AuthContext(user=membership.user, membership=membership, tenant=membership.tenant)


def require_roles(*roles: str):
    async def dependency(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if context.membership.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_role")
        return context

    return dependency
