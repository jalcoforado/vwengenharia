from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    refresh_expires_at,
    verify_password,
)
from app.models.audit import AuditEvent
from app.models.identity import Membership, RefreshToken, User
from app.modules.auth.schemas import TokenResponse


@dataclass(slots=True)
class AuthSelection:
    user: User
    membership: Membership


async def authenticate(
    session: AsyncSession, *, email: str, password: str, tenant_id: UUID | None
) -> AuthSelection:
    result = await session.execute(select(User).where(User.email == email.lower().strip()))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    stmt = (
        select(Membership)
        .options(selectinload(Membership.tenant))
        .where(Membership.user_id == user.id, Membership.is_active.is_(True))
    )
    if tenant_id is not None:
        stmt = stmt.where(Membership.tenant_id == tenant_id)
    memberships = list((await session.execute(stmt)).scalars().all())
    memberships = [item for item in memberships if item.tenant.is_active]

    if not memberships:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no_active_membership")
    if tenant_id is None and len(memberships) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="tenant_selection_required"
        )

    return AuthSelection(user=user, membership=memberships[0])


async def issue_tokens(
    session: AsyncSession, *, user: User, membership: Membership, audit_action: str
) -> TokenResponse:
    raw_refresh = new_refresh_token()
    record = RefreshToken(
        user_id=user.id,
        membership_id=membership.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=refresh_expires_at(),
        created_at=datetime.now(UTC),
    )
    session.add(record)
    session.add(
        AuditEvent(
            tenant_id=membership.tenant_id,
            actor_user_id=user.id,
            action=audit_action,
            entity_type="auth",
            entity_id=str(membership.id),
            event_metadata={"role": membership.role},
        )
    )
    await session.commit()

    return TokenResponse(
        access_token=create_access_token(
            user_id=user.id,
            membership_id=membership.id,
            tenant_id=membership.tenant_id,
            role=membership.role,
        ),
        refresh_token=raw_refresh,
        expires_in=settings.access_token_minutes * 60,
        tenant_id=membership.tenant_id,
        role=membership.role,
    )


async def rotate_refresh_token(session: AsyncSession, *, raw_token: str) -> TokenResponse:
    token_hash = hash_refresh_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    record = (await session.execute(stmt)).scalar_one_or_none()

    now = datetime.now(UTC)
    if record is None or record.revoked_at is not None or record.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token"
        )

    membership = (
        await session.execute(
            select(Membership)
            .options(selectinload(Membership.user), selectinload(Membership.tenant))
            .where(Membership.id == record.membership_id)
        )
    ).scalar_one_or_none()
    if (
        membership is None
        or not membership.is_active
        or not membership.user.is_active
        or not membership.tenant.is_active
        or membership.user_id != record.user_id
    ):
        record.revoked_at = now
        await session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="inactive_membership")

    record.revoked_at = now
    raw_refresh = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=membership.user_id,
            membership_id=membership.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_expires_at(),
            created_at=now,
        )
    )
    session.add(
        AuditEvent(
            tenant_id=membership.tenant_id,
            actor_user_id=membership.user_id,
            action="AUTH_REFRESH",
            entity_type="auth",
            entity_id=str(membership.id),
            event_metadata={"role": membership.role},
        )
    )
    await session.commit()

    return TokenResponse(
        access_token=create_access_token(
            user_id=membership.user_id,
            membership_id=membership.id,
            tenant_id=membership.tenant_id,
            role=membership.role,
        ),
        refresh_token=raw_refresh,
        expires_in=settings.access_token_minutes * 60,
        tenant_id=membership.tenant_id,
        role=membership.role,
    )
