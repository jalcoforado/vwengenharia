import asyncio
import os
import re

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.identity import Membership, Role, Tenant, User
from app.modules.team.service import ensure_collaborator_for_membership


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def normalize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise RuntimeError("BOOTSTRAP_TENANT_SLUG is invalid")
    return slug


async def main() -> None:
    tenant_name = required("BOOTSTRAP_TENANT_NAME")
    tenant_slug = normalize_slug(required("BOOTSTRAP_TENANT_SLUG"))
    email = required("BOOTSTRAP_ADMIN_EMAIL").lower()
    name = required("BOOTSTRAP_ADMIN_NAME")
    password = required("BOOTSTRAP_ADMIN_PASSWORD")
    if len(password) < 12:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters")

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name=tenant_name, slug=tenant_slug)
            session.add(tenant)
            await session.flush()

        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(email=email, name=name, password_hash=hash_password(password))
            session.add(user)
            await session.flush()

        membership = (
            await session.execute(
                select(Membership).where(
                    Membership.tenant_id == tenant.id,
                    Membership.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if membership is None:
            membership = Membership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=Role.ADMIN.value,
            )
            session.add(membership)
            await session.flush()
        await ensure_collaborator_for_membership(session, membership, user)

        await session.commit()
        print(f"Bootstrap complete for tenant={tenant.slug} admin={user.email}")


if __name__ == "__main__":
    asyncio.run(main())
