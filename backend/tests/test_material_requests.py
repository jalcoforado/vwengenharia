from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import Visit
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Client, Development, Station


@pytest.mark.asyncio
async def test_material_request_from_field_to_fulfillment() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"materials-admin-{suffix}@example.com"
    tech_email = f"materials-tech-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"VW Materials {suffix}", slug=f"vw-mat-{suffix}")
        admin = User(
            email=admin_email,
            name="Gestor Materiais",
            password_hash=hash_password(password),
        )
        tech = User(
            email=tech_email,
            name="Tecnico Campo",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, admin, tech])
        await session.flush()

        admin_membership = Membership(
            tenant_id=tenant.id,
            user_id=admin.id,
            role=Role.ADMIN.value,
        )
        tech_membership = Membership(
            tenant_id=tenant.id,
            user_id=tech.id,
            role=Role.TECNICO.value,
        )
        session.add_all([admin_membership, tech_membership])
        await session.flush()

        client = Client(tenant_id=tenant.id, name=f"Cliente {suffix}")
        session.add(client)
        await session.flush()
        development = Development(
            tenant_id=tenant.id,
            client_id=client.id,
            name=f"Empreendimento {suffix}",
        )
        session.add(development)
        await session.flush()
        station = Station(
            tenant_id=tenant.id,
            development_id=development.id,
            name=f"ETE {suffix}",
            is_active=True,
        )
        session.add(station)
        await session.flush()

        visit = Visit(
            tenant_id=tenant.id,
            station_id=station.id,
            technician_membership_id=tech_membership.id,
            scheduled_for=datetime.now(UTC),
            status="EM_EXECUCAO",
        )
        session.add(visit)
        await session.commit()
        station_id = station.id
        visit_id = visit.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        tech_login = await http.post(
            "/api/v1/auth/login",
            json={"email": tech_email, "password": password},
        )
        assert tech_login.status_code == 200
        tech_headers = {
            "Authorization": f"Bearer {tech_login.json()['access_token']}"
        }

        created = await http.post(
            "/api/v1/material-requests",
            headers=tech_headers,
            json={
                "station_id": str(station_id),
                "visit_id": str(visit_id),
                "category": "MATERIAL",
                "item_name": "Pastilha de cloro",
                "quantity": "2",
                "unit": "un",
                "priority": "ALTA",
                "notes": "Dosador sem reposicao.",
            },
        )
        assert created.status_code == 201
        request_id = created.json()["id"]
        assert created.json()["status"] == "SOLICITADA"

        admin_login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": password},
        )
        assert admin_login.status_code == 200
        admin_headers = {
            "Authorization": f"Bearer {admin_login.json()['access_token']}"
        }

        listed = await http.get(
            "/api/v1/material-requests",
            headers=admin_headers,
        )
        assert listed.status_code == 200
        assert any(item["id"] == request_id for item in listed.json())

        approved = await http.patch(
            f"/api/v1/material-requests/{request_id}",
            headers=admin_headers,
            json={"status": "APROVADA"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "APROVADA"

        buying = await http.patch(
            f"/api/v1/material-requests/{request_id}",
            headers=admin_headers,
            json={"status": "EM_COMPRA"},
        )
        assert buying.status_code == 200

        fulfilled = await http.patch(
            f"/api/v1/material-requests/{request_id}",
            headers=admin_headers,
            json={
                "status": "ATENDIDA",
                "notes": "Material entregue ao tecnico.",
            },
        )
        assert fulfilled.status_code == 200
        assert fulfilled.json()["status"] == "ATENDIDA"


@pytest.mark.asyncio
async def test_field_material_request_requires_assigned_visit() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    email = f"materials-field-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"VW Materials Field {suffix}", slug=f"vw-mf-{suffix}")
        user = User(
            email=email,
            name="Tecnico",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, user])
        await session.flush()
        session.add(
            Membership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=Role.TECNICO.value,
            )
        )
        client = Client(tenant_id=tenant.id, name=f"Cliente {suffix}")
        session.add(client)
        await session.flush()
        development = Development(
            tenant_id=tenant.id,
            client_id=client.id,
            name=f"Emp {suffix}",
        )
        session.add(development)
        await session.flush()
        station = Station(
            tenant_id=tenant.id,
            development_id=development.id,
            name=f"ETE {suffix}",
            is_active=True,
        )
        session.add(station)
        await session.commit()
        station_id = station.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = await http.post(
            "/api/v1/material-requests",
            headers=headers,
            json={
                "station_id": str(station_id),
                "category": "MATERIAL",
                "item_name": "Mangueira",
                "priority": "MEDIA",
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "field_request_requires_visit"
