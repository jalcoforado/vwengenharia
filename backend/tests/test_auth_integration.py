from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User


@pytest.mark.asyncio
async def test_login_tenant_boundary_and_refresh_rotation() -> None:
    suffix = uuid4().hex[:10]
    email = f"auth-{suffix}@example.com"
    password = "senha-segura-123"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Tenant A {suffix}", slug=f"tenant-a-{suffix}")
        tenant_b = Tenant(name=f"Tenant B {suffix}", slug=f"tenant-b-{suffix}")
        user = User(email=email, name="Usuario Teste", password_hash=hash_password(password))
        session.add_all([tenant_a, tenant_b, user])
        await session.flush()
        membership_a = Membership(
            tenant_id=tenant_a.id,
            user_id=user.id,
            role=Role.ADMIN.value,
        )
        membership_b = Membership(
            tenant_id=tenant_b.id,
            user_id=user.id,
            role=Role.TECNICO.value,
        )
        session.add_all([membership_a, membership_b])
        await session.commit()
        tenant_a_id = tenant_a.id
        tenant_b_id = tenant_b.id
        membership_a_id = membership_a.id
        user_id = user.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ambiguous = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert ambiguous.status_code == 409
        assert ambiguous.json()["detail"] == "tenant_selection_required"

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password, "tenant_id": str(tenant_a_id)},
        )
        assert login.status_code == 200
        tokens = login.json()
        assert tokens["tenant_id"] == str(tenant_a_id)
        assert tokens["role"] == Role.ADMIN.value
        set_cookie = login.headers.get("set-cookie", "")
        assert "mw_refresh=" in set_cookie
        assert "HttpOnly" in set_cookie

        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["tenant"]["id"] == str(tenant_a_id)

        forged_cross_tenant = create_access_token(
            user_id=user_id,
            membership_id=membership_a_id,
            tenant_id=tenant_b_id,
            role=Role.ADMIN.value,
        )
        denied = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {forged_cross_tenant}"},
        )
        assert denied.status_code == 401

        first_refresh = tokens["refresh_token"]
        rotated = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first_refresh},
        )
        assert rotated.status_code == 200
        assert rotated.json()["refresh_token"] != first_refresh

        replay = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first_refresh},
        )
        assert replay.status_code == 401

        logout = await client.post("/api/v1/auth/logout")
        assert logout.status_code == 204

        revoked_cookie = await client.post("/api/v1/auth/refresh", json={})
        assert revoked_cookie.status_code == 401
