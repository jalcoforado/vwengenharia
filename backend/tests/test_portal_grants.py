from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import Visit
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import ClientMembershipAccess, Station


async def login(http: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_portal_shows_only_explicitly_granted_developments() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"grant-admin-{suffix}@example.com"
    gestor_email = f"grant-gestor-{suffix}@example.com"
    portal_email = f"grant-portal-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Liberacao {suffix}", slug=f"liberacao-{suffix}")
        users = [
            User(email=email, name=name, password_hash=hash_password(password))
            for email, name in (
                (admin_email, "Admin"),
                (gestor_email, "Gestor"),
                (portal_email, "Responsavel Portal"),
            )
        ]
        session.add_all([tenant, *users])
        await session.flush()
        memberships = [
            Membership(tenant_id=tenant.id, user_id=user.id, role=role)
            for user, role in zip(
                users,
                (Role.ADMIN.value, Role.GESTOR.value, Role.CLIENTE.value),
                strict=True,
            )
        ]
        session.add_all(memberships)
        await session.commit()
        tenant_id = tenant.id
        portal_membership_id = memberships[2].id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        admin = await login(http, admin_email, password)
        gestor = await login(http, gestor_email, password)
        portal = await login(http, portal_email, password)

        async def create(path: str, body: dict) -> dict:
            response = await http.post(path, headers=admin, json=body)
            assert response.status_code == 201, response.text
            return response.json()

        maria = await create("/api/v1/clients", {"name": f"Maria {suffix}"})
        joao = await create("/api/v1/clients", {"name": f"Joao {suffix}"})

        # Maria e principal de dois empreendimentos e adicional de um terceiro.
        lago = await create(
            "/api/v1/developments",
            {"client_id": maria["id"], "name": f"Lago {suffix}", "document": f"CNPJ-{suffix}"},
        )
        serra = await create(
            "/api/v1/developments", {"client_id": maria["id"], "name": f"Serra {suffix}"}
        )
        mar = await create(
            "/api/v1/developments", {"client_id": joao["id"], "name": f"Mar {suffix}"}
        )
        assert lago["document"] == f"CNPJ-{suffix}"

        repeated_document = await http.post(
            "/api/v1/developments",
            headers=admin,
            json={"client_id": maria["id"], "name": "Repetido", "document": f"CNPJ-{suffix}"},
        )
        assert repeated_document.status_code == 409

        maria_no_mar = await create(
            "/api/v1/client-contacts",
            {"client_id": maria["id"], "development_id": mar["id"], "scope": "FINANCEIRO"},
        )

        async with session_factory() as session:
            for development, code in ((lago, "LAGO"), (serra, "SERRA"), (mar, "MAR")):
                station = Station(
                    tenant_id=tenant_id,
                    development_id=UUID(development["id"]),
                    name=f"Estacao {code}",
                    code=f"{code}-{suffix}",
                )
                session.add(station)
                await session.flush()
                session.add(
                    Visit(
                        tenant_id=tenant_id,
                        station_id=station.id,
                        technician_membership_id=portal_membership_id,
                        scheduled_for=datetime.now(UTC),
                        status="REVISADA",
                    )
                )
            # O login do portal pertence a Maria.
            session.add(
                ClientMembershipAccess(
                    tenant_id=tenant_id,
                    membership_id=portal_membership_id,
                    client_id=UUID(maria["id"]),
                )
            )
            await session.commit()

        async def stations() -> set[str]:
            response = await http.get("/api/v1/client-portal", headers=portal)
            assert response.status_code == 200
            return {item["name"] for item in response.json()["stations"]}

        # Ser principal ou adicional nao basta: nada foi liberado ainda.
        assert await stations() == set()

        links = (
            await http.get(
                "/api/v1/client-contacts", headers=admin, params={"client_id": maria["id"]}
            )
        ).json()
        primary_lago = next(
            item for item in links if item["development_id"] == lago["id"] and item["is_primary"]
        )
        primary_serra = next(
            item for item in links if item["development_id"] == serra["id"] and item["is_primary"]
        )

        cannot_deactivate_primary = await http.patch(
            f"/api/v1/client-contacts/{primary_lago['id']}",
            headers=admin,
            json={"is_active": False},
        )
        assert cannot_deactivate_primary.status_code == 409

        # Conceder acesso ao portal exige administrador.
        denied = await http.patch(
            f"/api/v1/client-contacts/{primary_lago['id']}",
            headers=gestor,
            json={"portal_access": True},
        )
        assert denied.status_code == 403
        denied_on_create = await http.post(
            "/api/v1/client-contacts",
            headers=gestor,
            json={
                "client_id": maria["id"],
                "development_id": serra["id"],
                "scope": "TECNICO",
                "portal_access": True,
            },
        )
        assert denied_on_create.status_code == 403

        granted = await http.patch(
            f"/api/v1/client-contacts/{primary_lago['id']}",
            headers=admin,
            json={"portal_access": True},
        )
        assert granted.status_code == 200
        assert granted.json()["portal_access"] is True
        assert await stations() == {"Estacao LAGO"}

        # Responsavel adicional tambem pode ser liberado.
        granted_additional = await http.patch(
            f"/api/v1/client-contacts/{maria_no_mar['id']}",
            headers=admin,
            json={"portal_access": True},
        )
        assert granted_additional.status_code == 200
        assert await stations() == {"Estacao LAGO", "Estacao MAR"}

        portal_payload = (await http.get("/api/v1/client-portal", headers=portal)).json()
        visits_by_station = {item["station_id"]: item["id"] for item in portal_payload["visits"]}
        assert len(visits_by_station) == 2

        async with session_factory() as session:
            serra_visit_id = await session.scalar(
                select(Visit.id)
                .join(Station, Station.id == Visit.station_id)
                .where(Station.development_id == UUID(serra["id"]))
            )
        hidden_report = await http.get(
            f"/api/v1/reports/visits/{serra_visit_id}.html", headers=portal
        )
        assert hidden_report.status_code == 404
        visible_report = await http.get(
            f"/api/v1/reports/visits/{next(iter(visits_by_station.values()))}.html",
            headers=portal,
        )
        assert visible_report.status_code == 200

        # Quem cadastra pode revogar; ao inativar a responsabilidade o portal fecha.
        revoked = await http.patch(
            f"/api/v1/client-contacts/{maria_no_mar['id']}",
            headers=gestor,
            json={"is_active": False},
        )
        assert revoked.status_code == 200
        assert revoked.json()["portal_access"] is False
        assert await stations() == {"Estacao LAGO"}

        # Trocar o principal: Maria continua responsavel, mas perde a visao no portal.
        changed = await http.patch(
            f"/api/v1/developments/{lago['id']}",
            headers=admin,
            json={"client_id": joao["id"]},
        )
        assert changed.status_code == 200
        lago_links = (
            await http.get(
                "/api/v1/client-contacts",
                headers=admin,
                params={"development_id": lago["id"]},
            )
        ).json()
        assert {
            (item["client_id"], item["is_primary"], item["portal_access"]) for item in lago_links
        } == {(maria["id"], False, False), (joao["id"], True, False)}
        assert await stations() == set()

        # Voltar o principal reaproveita a responsabilidade que ja existia.
        restored = await http.patch(
            f"/api/v1/developments/{lago['id']}",
            headers=admin,
            json={"client_id": maria["id"]},
        )
        assert restored.status_code == 200
        lago_links = (
            await http.get(
                "/api/v1/client-contacts",
                headers=admin,
                params={"development_id": lago["id"]},
            )
        ).json()
        assert {(item["client_id"], item["is_primary"]) for item in lago_links} == {
            (maria["id"], True),
            (joao["id"], False),
        }
        assert primary_serra["portal_access"] is False
