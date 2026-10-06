from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.models.identity import Membership, RefreshToken, Role, User
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit
from app.modules.team.schemas import TeamMemberCreate, TeamMemberUpdate


def _can_manage_role(actor_role: str, target_role: str) -> bool:
    if target_role == Role.SUPERADMIN.value:
        return actor_role == Role.SUPERADMIN.value
    return actor_role in {Role.SUPERADMIN.value, Role.ADMIN.value}


async def list_team_members(
    session: AsyncSession,
    context: AuthContext,
    *,
    active_only: bool = False,
    roles: set[str] | None = None,
) -> list[Membership]:
    stmt = (
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.tenant_id == context.tenant.id)
    )
    if active_only:
        stmt = stmt.where(Membership.is_active.is_(True))
    if roles:
        stmt = stmt.where(Membership.role.in_(roles))
    stmt = stmt.order_by(User.name)
    return list((await session.execute(stmt.join(User))).scalars().all())


async def create_team_member(
    session: AsyncSession,
    context: AuthContext,
    payload: TeamMemberCreate,
) -> Membership:
    role = payload.role.value
    if not _can_manage_role(context.membership.role, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot_assign_role",
        )

    email = str(payload.email).lower().strip()
    existing_user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email_already_registered",
        )

    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(user)
    await session.flush()

    membership = Membership(
        tenant_id=context.tenant.id,
        user_id=user.id,
        role=role,
        is_active=True,
    )
    session.add(membership)
    await session.flush()

    add_audit(
        session,
        context,
        action="TEAM_MEMBER_CREATE",
        entity_type="membership",
        entity_id=membership.id,
        fields=["email", "name", "role"],
    )
    await session.commit()

    stmt = (
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.id == membership.id)
    )
    return (await session.execute(stmt)).scalar_one()


async def update_team_member(
    session: AsyncSession,
    context: AuthContext,
    membership_id: UUID,
    payload: TeamMemberUpdate,
) -> Membership:
    membership = (
        await session.execute(
            select(Membership)
            .options(selectinload(Membership.user))
            .where(
                Membership.id == membership_id,
                Membership.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member_not_found")

    if membership.role == Role.SUPERADMIN.value and context.membership.role != Role.SUPERADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot_manage_superadmin",
        )

    changes = payload.model_dump(exclude_unset=True)
    if membership.id == context.membership.id and (
        "role" in changes or changes.get("is_active") is False
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot_change_own_membership",
        )

    if "role" in changes:
        role = changes["role"]
        if isinstance(role, Role):
            role = role.value
        if not _can_manage_role(context.membership.role, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="cannot_assign_role",
            )
        membership.role = role

    if "is_active" in changes:
        membership.is_active = bool(changes["is_active"])

    add_audit(
        session,
        context,
        action="TEAM_MEMBER_UPDATE",
        entity_type="membership",
        entity_id=membership.id,
        fields=sorted(changes.keys()),
    )
    await session.commit()
    await session.refresh(membership)
    return membership


async def change_own_password(
    session: AsyncSession,
    context: AuthContext,
    *,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, context.user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="current_password_invalid",
        )
    if current_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="new_password_must_differ",
        )

    context.user.password_hash = hash_password(new_password)
    now = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == context.user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    add_audit(
        session,
        context,
        action="PASSWORD_CHANGE",
        entity_type="user",
        entity_id=context.user.id,
        fields=["password_hash"],
    )
    await session.commit()
