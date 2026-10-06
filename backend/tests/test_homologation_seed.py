import os
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.db.session import get_session_factory
from app.models.identity import Role, Tenant, User
from scripts import seed_homologation


@pytest.mark.asyncio
async def test_homologation_seed_resets_existing_demo_password(monkeypatch) -> None:
    suffix = uuid4().hex[:10]
    slug = f"homolog-seed-{suffix}"
    email = f"homolog-admin-{suffix}@example.com"
    first_password = "Primeira-Senha-HML-2026!"
    second_password = "Segunda-Senha-HML-2026!"

    monkeypatch.setenv("HOMOLOGATION_TENANT_SLUG", slug)
    monkeypatch.setenv("HOMOLOGATION_TENANT_NAME", f"Homolog Seed {suffix}")
    monkeypatch.setenv("HOMOLOGATION_ADMIN_EMAIL", email)
    monkeypatch.setenv(
        "HOMOLOGATION_TECH_EMAIL",
        f"homolog-tech-{suffix}@example.com",
    )
    monkeypatch.setenv(
        "HOMOLOGATION_MAINTENANCE_EMAIL",
        f"homolog-maint-{suffix}@example.com",
    )
    monkeypatch.setenv("HOMOLOGATION_PASSWORD", first_password)

    await seed_homologation.main()

    session_factory = get_session_factory()
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
        assert verify_password(first_password, user.password_hash)

    monkeypatch.setenv("HOMOLOGATION_PASSWORD", second_password)
    await seed_homologation.main()

    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
        assert verify_password(second_password, user.password_hash)
        assert not verify_password(first_password, user.password_hash)

        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one()
        assert tenant.is_active is True
