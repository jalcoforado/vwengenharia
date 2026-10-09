from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Collaborator, Membership, Role, Tenant, User

PASSWORD = "senha-segura-123"


async def login(http: AsyncClient, email: str, expected: int = 200) -> dict[str, str]:
    response = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == expected
    if expected != 200:
        return {}
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def seed_tenant(suffix: str) -> tuple[str, str]:
    admin_email = f"colab-admin-{suffix}@example.com"
    gestor_email = f"colab-gestor-{suffix}@example.com"
    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Colaboradores {suffix}", slug=f"colab-{suffix}")
        admin = User(email=admin_email, name="Admin", password_hash=hash_password(PASSWORD))
        gestor = User(email=gestor_email, name="Gestor", password_hash=hash_password(PASSWORD))
        session.add_all([tenant, admin, gestor])
        await session.flush()
        session.add_all(
            [
                Membership(tenant_id=tenant.id, user_id=admin.id, role=Role.ADMIN.value),
                Membership(tenant_id=tenant.id, user_id=gestor.id, role=Role.GESTOR.value),
            ]
        )
        await session.commit()
    return admin_email, gestor_email


@pytest.mark.asyncio
async def test_collaborator_credential_is_optional_and_bound_to_collaborator() -> None:
    suffix = uuid4().hex[:10]
    admin_email, gestor_email = await seed_tenant(suffix)
    tech_email = f"colab-tech-{suffix}@example.com"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        admin = await login(http, admin_email)
        gestor = await login(http, gestor_email)

        # Colaborador sem credencial: existe no cadastro e nao entra no app.
        director = await http.post(
            "/api/v1/collaborators",
            headers=admin,
            json={
                "name": f"Diretora {suffix}",
                "document": f"CPF-D-{suffix}",
                "category": "DIRETORIA",
                "contact_whatsapp": "(85) 99999-0000",
            },
        )
        assert director.status_code == 201
        assert director.json()["membership_id"] is None
        assert director.json()["credential_email"] is None

        repeated = await http.post(
            "/api/v1/collaborators",
            headers=admin,
            json={"name": "Outro", "document": f"CPF-D-{suffix}", "category": "BACKOFFICE"},
        )
        assert repeated.status_code == 409

        only_admin_writes = await http.post(
            "/api/v1/collaborators",
            headers=gestor,
            json={"name": "Sem permissao", "category": "TECNICO"},
        )
        assert only_admin_writes.status_code == 403
        assert (await http.get("/api/v1/collaborators", headers=gestor)).status_code == 200

        technician = await http.post(
            "/api/v1/collaborators",
            headers=admin,
            json={"name": f"Tecnico {suffix}", "category": "TECNICO"},
        )
        assert technician.status_code == 201
        technician_id = technician.json()["id"]

        credential = await http.post(
            f"/api/v1/collaborators/{technician_id}/credential",
            headers=admin,
            json={"email": tech_email, "password": PASSWORD, "role": "TECNICO"},
        )
        assert credential.status_code == 201
        assert credential.json()["credential_email"] == tech_email
        assert credential.json()["credential_role"] == "TECNICO"
        assert credential.json()["credential_active"] is True
        membership_id = credential.json()["membership_id"]

        second_credential = await http.post(
            f"/api/v1/collaborators/{technician_id}/credential",
            headers=admin,
            json={
                "email": f"colab-dup-{suffix}@example.com",
                "password": PASSWORD,
                "role": "TECNICO",
            },
        )
        assert second_credential.status_code == 409
        assert second_credential.json()["detail"] == "collaborator_already_has_credential"

        client_role = await http.post(
            f"/api/v1/collaborators/{director.json()['id']}/credential",
            headers=admin,
            json={
                "email": f"colab-cli-{suffix}@example.com",
                "password": PASSWORD,
                "role": "CLIENTE",
            },
        )
        assert client_role.status_code == 422

        tech = await login(http, tech_email)
        assert (await http.get("/api/v1/auth/me", headers=tech)).status_code == 200

        # Inativar o colaborador bloqueia a credencial.
        deactivated = await http.patch(
            f"/api/v1/collaborators/{technician_id}",
            headers=admin,
            json={"is_active": False},
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["credential_active"] is False
        await login(http, tech_email, expected=403)

        blocked_reactivation = await http.patch(
            f"/api/v1/team/{membership_id}",
            headers=admin,
            json={"is_active": True},
        )
        assert blocked_reactivation.status_code == 409
        assert blocked_reactivation.json()["detail"] == "collaborator_inactive"

        # Reativar o colaborador nao devolve o acesso sozinho.
        reactivated = await http.patch(
            f"/api/v1/collaborators/{technician_id}",
            headers=admin,
            json={"is_active": True},
        )
        assert reactivated.json()["is_active"] is True
        assert reactivated.json()["credential_active"] is False
        restored = await http.patch(
            f"/api/v1/team/{membership_id}",
            headers=admin,
            json={"is_active": True},
        )
        assert restored.status_code == 200
        await login(http, tech_email)

        # Credencial criada direto pela API de equipe registra o colaborador dela.
        direct_email = f"colab-direct-{suffix}@example.com"
        direct = await http.post(
            "/api/v1/team",
            headers=admin,
            json={
                "email": direct_email,
                "name": "Supervisor Direto",
                "password": PASSWORD,
                "role": "SUPERVISOR",
            },
        )
        assert direct.status_code == 201
        listed = (await http.get("/api/v1/collaborators", headers=admin)).json()
        direct_collaborator = next(
            item for item in listed if item["credential_email"] == direct_email
        )
        assert direct_collaborator["category"] == "BACKOFFICE"
        assert direct_collaborator["name"] == "Supervisor Direto"

        portal_through_team = await http.post(
            "/api/v1/team",
            headers=admin,
            json={
                "email": f"colab-portal-{suffix}@example.com",
                "name": "Portal",
                "password": PASSWORD,
                "role": "CLIENTE",
            },
        )
        assert portal_through_team.status_code == 422
        assert portal_through_team.json()["detail"] == "client_credential_requires_responsible"


@pytest.mark.asyncio
async def test_portal_credential_is_created_from_the_responsible() -> None:
    suffix = uuid4().hex[:10]
    admin_email, gestor_email = await seed_tenant(suffix)
    portal_email = f"colab-resp-{suffix}@example.com"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        admin = await login(http, admin_email)
        gestor = await login(http, gestor_email)

        responsible = await http.post(
            "/api/v1/clients", headers=admin, json={"name": f"Sindica {suffix}"}
        )
        assert responsible.status_code == 201
        client_id = responsible.json()["id"]
        development = await http.post(
            "/api/v1/developments",
            headers=admin,
            json={"client_id": client_id, "name": f"Condominio {suffix}"},
        )
        assert development.status_code == 201

        forbidden = await http.post(
            f"/api/v1/clients/{client_id}/portal-credential",
            headers=gestor,
            json={"email": portal_email, "password": PASSWORD},
        )
        assert forbidden.status_code == 403

        created = await http.post(
            f"/api/v1/clients/{client_id}/portal-credential",
            headers=admin,
            json={"email": portal_email, "password": PASSWORD},
        )
        assert created.status_code == 201
        assert created.json()["client_id"] == client_id
        assert created.json()["user_email"] == portal_email

        again = await http.post(
            f"/api/v1/clients/{client_id}/portal-credential",
            headers=admin,
            json={"email": f"colab-resp2-{suffix}@example.com", "password": PASSWORD},
        )
        assert again.status_code == 409

        accesses = (await http.get("/api/v1/client-access", headers=admin)).json()
        assert [(item["client_id"], item["user_email"]) for item in accesses] == [
            (client_id, portal_email)
        ]

        # O login existe, mas nada aparece ate o empreendimento ser liberado.
        portal = await login(http, portal_email)
        empty = await http.get("/api/v1/client-portal", headers=portal)
        assert empty.status_code == 200
        assert [item["id"] for item in empty.json()["clients"]] == [client_id]
        assert empty.json()["stations"] == []

    session_factory = get_session_factory()
    async with session_factory() as session:
        portal_user = await session.scalar(select(User).where(User.email == portal_email))
        membership = await session.scalar(
            select(Membership).where(Membership.user_id == portal_user.id)
        )
        assert membership.role == Role.CLIENTE.value
        collaborator = await session.scalar(
            select(Collaborator).where(Collaborator.membership_id == membership.id)
        )
        # Login de portal pertence ao responsavel, nao vira colaborador.
        assert collaborator is None
