from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import Visit
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import (
    Client,
    ClientDevelopmentContact,
    ClientMembershipAccess,
    Development,
    Station,
)


async def login(http: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_client_portal_is_scoped_to_explicit_access() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    client_email = f"portal-client-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Portal {suffix}", slug=f"portal-{suffix}")
        user = User(
            email=client_email,
            name="Cliente Portal",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, user])
        await session.flush()

        membership = Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=Role.CLIENTE.value,
        )
        allowed_client = Client(tenant_id=tenant.id, name=f"Permitido {suffix}")
        denied_client = Client(tenant_id=tenant.id, name=f"Negado {suffix}")
        session.add_all([membership, allowed_client, denied_client])
        await session.flush()

        allowed_development = Development(
            tenant_id=tenant.id,
            client_id=allowed_client.id,
            name="Empreendimento permitido",
        )
        denied_development = Development(
            tenant_id=tenant.id,
            client_id=denied_client.id,
            name="Empreendimento negado",
        )
        session.add_all([allowed_development, denied_development])
        await session.flush()

        # Os dois empreendimentos estao liberados para o portal dos seus principais;
        # o login abaixo so esta ligado ao responsavel permitido.
        session.add_all(
            [
                ClientDevelopmentContact(
                    tenant_id=tenant.id,
                    client_id=development.client_id,
                    development_id=development.id,
                    scope="GERAL",
                    is_primary=True,
                    portal_access=True,
                )
                for development in (allowed_development, denied_development)
            ]
        )
        await session.flush()

        allowed_station = Station(
            tenant_id=tenant.id,
            development_id=allowed_development.id,
            name="Estacao permitida",
            code="PORTAL-OK",
        )
        denied_station = Station(
            tenant_id=tenant.id,
            development_id=denied_development.id,
            name="Estacao negada",
            code="PORTAL-NO",
        )
        session.add_all([allowed_station, denied_station])
        await session.flush()

        access = ClientMembershipAccess(
            tenant_id=tenant.id,
            membership_id=membership.id,
            client_id=allowed_client.id,
        )
        allowed_visit = Visit(
            tenant_id=tenant.id,
            station_id=allowed_station.id,
            technician_membership_id=membership.id,
            scheduled_for=datetime.now(UTC),
            status="REVISADA",
        )
        denied_visit = Visit(
            tenant_id=tenant.id,
            station_id=denied_station.id,
            technician_membership_id=membership.id,
            scheduled_for=datetime.now(UTC),
            status="REVISADA",
        )
        session.add_all([access, allowed_visit, denied_visit])
        await session.commit()

        allowed_visit_id = str(allowed_visit.id)
        denied_visit_id = str(denied_visit.id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        headers = await login(http, client_email, password)

        portal = await http.get("/api/v1/client-portal", headers=headers)
        assert portal.status_code == 200
        payload = portal.json()

        assert [item["name"] for item in payload["clients"]] == [f"Permitido {suffix}"]
        assert [item["name"] for item in payload["stations"]] == ["Estacao permitida"]
        visit_ids = {item["id"] for item in payload["visits"]}
        assert allowed_visit_id in visit_ids
        assert denied_visit_id not in visit_ids

        allowed_report = await http.get(
            f"/api/v1/reports/visits/{allowed_visit_id}.html",
            headers=headers,
        )
        assert allowed_report.status_code == 200

        denied_report = await http.get(
            f"/api/v1/reports/visits/{denied_visit_id}.html",
            headers=headers,
        )
        assert denied_report.status_code == 404
