from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Client


@pytest.mark.asyncio
async def test_integration_key_is_tenant_scoped_incremental_and_revocable() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"integration-admin-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Tenant A {suffix}", slug=f"int-a-{suffix}")
        tenant_b = Tenant(name=f"Tenant B {suffix}", slug=f"int-b-{suffix}")
        admin = User(
            email=admin_email,
            name="Admin Integracao",
            password_hash=hash_password(password),
        )
        session.add_all([tenant_a, tenant_b, admin])
        await session.flush()
        membership = Membership(
            tenant_id=tenant_a.id,
            user_id=admin.id,
            role=Role.ADMIN.value,
        )
        session.add(membership)
        session.add_all(
            [
                Client(tenant_id=tenant_a.id, name=f"Cliente A {suffix}"),
                Client(tenant_id=tenant_b.id, name=f"Cliente B {suffix}"),
            ]
        )
        await session.commit()
        tenant_a_id = tenant_a.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": password},
        )
        assert login.status_code == 200
        admin_headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }

        created = await http.post(
            "/api/v1/integration-keys",
            headers=admin_headers,
            json={"name": "iAnalisys"},
        )
        assert created.status_code == 201
        secret = created.json()["secret"]
        key_id = created.json()["id"]
        assert secret.startswith("mwk_")
        assert created.json()["key_prefix"] == secret[:12]

        listed = await http.get("/api/v1/integration-keys", headers=admin_headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert "secret" not in listed.json()[0]

        integration_headers = {"X-Integration-Key": secret}
        exported = await http.get(
            "/api/v1/integration/v1/clients",
            headers=integration_headers,
        )
        assert exported.status_code == 200
        body = exported.json()
        assert body["schema_version"] == "1"
        assert body["tenant_id"] == str(tenant_a_id)
        assert [item["name"] for item in body["items"]] == [f"Cliente A {suffix}"]
        snapshot = body["generated_at"]

        invalid = await http.get(
            "/api/v1/integration/v1/clients",
            headers={"X-Integration-Key": "mwk_invalid"},
        )
        assert invalid.status_code == 401

        future_snapshot = await http.get(
            "/api/v1/integration/v1/clients",
            headers=integration_headers,
            params={"snapshot_at": "2999-01-01T00:00:00Z"},
        )
        assert future_snapshot.status_code == 422

        new_client = await http.post(
            "/api/v1/clients",
            headers=admin_headers,
            json={"name": f"Cliente A2 {suffix}"},
        )
        assert new_client.status_code == 201

        incremental = await http.get(
            "/api/v1/integration/v1/clients",
            headers=integration_headers,
            params={"updated_since": snapshot},
        )
        assert incremental.status_code == 200
        assert [item["name"] for item in incremental.json()["items"]] == [
            f"Cliente A2 {suffix}"
        ]

        revoked = await http.post(
            f"/api/v1/integration-keys/{key_id}/revoke",
            headers=admin_headers,
        )
        assert revoked.status_code == 200
        assert revoked.json()["revoked_at"] is not None

        after_revoke = await http.get(
            "/api/v1/integration/v1/clients",
            headers=integration_headers,
        )
        assert after_revoke.status_code == 401


@pytest.mark.asyncio
async def test_integration_export_rejects_naive_watermark() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    email = f"integration-naive-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Tenant {suffix}", slug=f"int-naive-{suffix}")
        user = User(email=email, name="Admin", password_hash=hash_password(password))
        session.add_all([tenant, user])
        await session.flush()
        session.add(
            Membership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=Role.ADMIN.value,
            )
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        created = await http.post(
            "/api/v1/integration-keys",
            headers=headers,
            json={"name": "sync"},
        )
        key_headers = {"X-Integration-Key": created.json()["secret"]}
        response = await http.get(
            "/api/v1/integration/v1/clients",
            headers=key_headers,
            params={"updated_since": datetime.now(UTC).replace(tzinfo=None).isoformat()},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "updated_since_must_include_timezone"
