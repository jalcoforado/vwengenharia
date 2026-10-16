from dataclasses import dataclass
from typing import Annotated
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
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass(slots=True)
class AuthContext:
    user: User
    membership: Membership
    tenant: Tenant


async def get_auth_context(
    credentials: BearerCredentials,
    session: SessionDep,
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


AuthContextDep = Annotated[AuthContext, Depends(get_auth_context)]


def require_roles(*roles: str, allow_password_change_pending: bool = False):
    async def dependency(context: AuthContextDep) -> AuthContext:
        if context.membership.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_role")
        # Com senha provisoria, so a troca de senha fica disponivel.
        if context.user.must_change_password and not allow_password_change_pending:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="password_change_required",
            )
        return context

    return dependency
