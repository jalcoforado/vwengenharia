from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.audit import AuditEvent
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Client


@pytest.mark.asyncio
async def test_core_registers_are_tenant_scoped_and_audited() -> None:
    suffix = uuid4().hex[:10]
    admin_email = f"admin-core-{suffix}@example.com"
    client_email = f"client-core-{suffix}@example.com"
    password = "senha-segura-123"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Operacao A {suffix}", slug=f"operacao-a-{suffix}")
        tenant_b = Tenant(name=f"Operacao B {suffix}", slug=f"operacao-b-{suffix}")
        admin = User(
            email=admin_email,
            name="Admin Operacao",
            password_hash=hash_password(password),
        )
        client_user = User(
            email=client_email,
            name="Cliente Portal",
            password_hash=hash_password(password),
        )
        session.add_all([tenant_a, tenant_b, admin, client_user])
        await session.flush()
        session.add_all(
            [
                Membership(
                    tenant_id=tenant_a.id,
                    user_id=admin.id,
                    role=Role.ADMIN.value,
                ),
                Membership(
                    tenant_id=tenant_a.id,
                    user_id=client_user.id,
                    role=Role.CLIENTE.value,
                ),
            ]
        )
        foreign_client = Client(
            tenant_id=tenant_b.id,
            name=f"Cliente Outro Tenant {suffix}",
        )
        session.add(foreign_client)
        await session.commit()
        tenant_a_id = tenant_a.id
        foreign_client_id = foreign_client.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": password},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        client = await http.post(
            "/api/v1/clients",
            headers=headers,
            json={"name": f"Cliente VW {suffix}", "document": f"DOC-{suffix}"},
        )
        assert client.status_code == 201
        client_id = client.json()["id"]

        hidden = await http.get(f"/api/v1/clients/{foreign_client_id}", headers=headers)
        assert hidden.status_code == 404

        rejected_parent = await http.post(
            "/api/v1/developments",
            headers=headers,
            json={"client_id": str(foreign_client_id), "name": "Nao deve criar"},
        )
        assert rejected_parent.status_code == 404

        development = await http.post(
            "/api/v1/developments",
            headers=headers,
            json={
                "client_id": client_id,
                "name": f"Empreendimento {suffix}",
                "city": "Fortaleza",
                "state": "CE",
            },
        )
        assert development.status_code == 201

        station = await http.post(
            "/api/v1/stations",
            headers=headers,
            json={
                "development_id": development.json()["id"],
                "name": f"ETE {suffix}",
                "code": f"ETE-{suffix}",
                "visit_frequency_days": 7,
            },
        )
        assert station.status_code == 201

        asset_type = await http.post(
            "/api/v1/asset-types",
            headers=headers,
            json={"name": f"Aerador {suffix}", "code": f"AER-{suffix}"},
        )
        assert asset_type.status_code == 201

        asset = await http.post(
            "/api/v1/assets",
            headers=headers,
            json={
                "station_id": station.json()["id"],
                "asset_type_id": asset_type.json()["id"],
                "name": "Aerador I",
                "status": "OPERANDO",
            },
        )
        assert asset.status_code == 201

        station_assets = await http.get(
            f"/api/v1/stations/{station.json()['id']}/assets", headers=headers
        )
        assert station_assets.status_code == 200
        assert [item["id"] for item in station_assets.json()] == [asset.json()["id"]]

        deactivated = await http.patch(
            f"/api/v1/clients/{client_id}",
            headers=headers,
            json={"is_active": False},
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False

        client_login = await http.post(
            "/api/v1/auth/login",
            json={"email": client_email, "password": password},
        )
        assert client_login.status_code == 200
        client_headers = {
            "Authorization": f"Bearer {client_login.json()['access_token']}"
        }
        denied = await http.get("/api/v1/clients", headers=client_headers)
        assert denied.status_code == 403

    async with session_factory() as session:
        audit_count = await session.scalar(
            select(func.count(AuditEvent.id)).where(AuditEvent.tenant_id == tenant_a_id)
        )
        assert audit_count is not None
        assert audit_count >= 7
