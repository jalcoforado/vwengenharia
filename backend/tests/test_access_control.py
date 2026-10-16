from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User

PASSWORD = "senha-segura-123"
PROVISIONAL = "provisoria-456789"
CHOSEN = "escolhida-pela-pessoa-1"


async def login(http: AsyncClient, email: str, password: str, expected: int = 200) -> dict[str, str]:
    response = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == expected
    if expected != 200:
        return {}
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_admin_lists_accesses_resets_password_and_user_must_change_it() -> None:
    suffix = uuid4().hex[:10]
    admin_email = f"acesso-admin-{suffix}@example.com"
    gestor_email = f"acesso-gestor-{suffix}@example.com"
    tech_email = f"acesso-tech-{suffix}@example.com"
    portal_email = f"acesso-portal-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Acessos {suffix}", slug=f"acessos-{suffix}")
        other_tenant = Tenant(name=f"Acessos Outro {suffix}", slug=f"acessos-outro-{suffix}")
        admin = User(email=admin_email, name="Admin", password_hash=hash_password(PASSWORD))
        gestor = User(email=gestor_email, name="Gestor", password_hash=hash_password(PASSWORD))
        outsider = User(
            email=f"acesso-fora-{suffix}@example.com",
            name="Outro Tenant",
            password_hash=hash_password(PASSWORD),
        )
        session.add_all([tenant, other_tenant, admin, gestor, outsider])
        await session.flush()
        admin_membership = Membership(tenant_id=tenant.id, user_id=admin.id, role=Role.ADMIN.value)
        outsider_membership = Membership(
            tenant_id=other_tenant.id, user_id=outsider.id, role=Role.TECNICO.value
        )
        session.add_all(
            [
                admin_membership,
                Membership(tenant_id=tenant.id, user_id=gestor.id, role=Role.GESTOR.value),
                outsider_membership,
            ]
        )
        await session.commit()
        admin_membership_id = str(admin_membership.id)
        outsider_membership_id = str(outsider_membership.id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        admin = await login(http, admin_email, PASSWORD)
        gestor = await login(http, gestor_email, PASSWORD)

        collaborator = await http.post(
            "/api/v1/collaborators",
            headers=admin,
            json={"name": f"Tecnica {suffix}", "category": "TECNICO"},
        )
        assert collaborator.status_code == 201
        credential = await http.post(
            f"/api/v1/collaborators/{collaborator.json()['id']}/credential",
            headers=admin,
            json={"email": tech_email, "password": PROVISIONAL, "role": "TECNICO"},
        )
        assert credential.status_code == 201
        tech_membership_id = credential.json()["membership_id"]

        responsible = await http.post(
            "/api/v1/clients", headers=admin, json={"name": f"Sindico {suffix}"}
        )
        portal_credential = await http.post(
            f"/api/v1/clients/{responsible.json()['id']}/portal-credential",
            headers=admin,
            json={"email": portal_email, "password": PROVISIONAL},
        )
        assert portal_credential.status_code == 201

        # A lista de acessos e so para administradores e so do proprio tenant.
        assert (await http.get("/api/v1/accesses", headers=gestor)).status_code == 403
        accesses = await http.get("/api/v1/accesses", headers=admin)
        assert accesses.status_code == 200
        by_email = {item["email"]: item for item in accesses.json()}
        assert set(by_email) == {admin_email, gestor_email, tech_email, portal_email}
        assert by_email[tech_email]["kind"] == "COLLABORATOR"
        assert by_email[tech_email]["linked_name"] == f"Tecnica {suffix}"
        assert by_email[tech_email]["role"] == "TECNICO"
        assert by_email[tech_email]["must_change_password"] is True
        assert by_email[portal_email]["kind"] == "RESPONSIBLE"
        assert by_email[portal_email]["linked_name"] == f"Sindico {suffix}"
        assert by_email[portal_email]["role"] == "CLIENTE"
        assert by_email[admin_email]["kind"] == "UNLINKED"
        assert by_email[admin_email]["must_change_password"] is False

        # Senha inicial e provisoria: entra, mas so consegue trocar a senha.
        tech = await login(http, tech_email, PROVISIONAL)
        me = await http.get("/api/v1/auth/me", headers=tech)
        assert me.status_code == 200
        assert me.json()["must_change_password"] is True
        blocked = await http.get("/api/v1/field/bootstrap", headers=tech)
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == "password_change_required"

        changed = await http.post(
            "/api/v1/auth/change-password",
            headers=tech,
            json={"current_password": PROVISIONAL, "new_password": CHOSEN},
        )
        assert changed.status_code == 204
        tech = await login(http, tech_email, CHOSEN)
        assert (await http.get("/api/v1/auth/me", headers=tech)).json()["must_change_password"] is False
        assert (await http.get("/api/v1/field/bootstrap", headers=tech)).status_code == 200

        # Redefinicao pelo administrador: a senha antiga deixa de valer e a nova e provisoria.
        short = await http.post(
            f"/api/v1/team/{tech_membership_id}/reset-password",
            headers=admin,
            json={"new_password": "curta"},
        )
        assert short.status_code == 422
        not_admin = await http.post(
            f"/api/v1/team/{tech_membership_id}/reset-password",
            headers=gestor,
            json={"new_password": PROVISIONAL},
        )
        assert not_admin.status_code == 403
        reset = await http.post(
            f"/api/v1/team/{tech_membership_id}/reset-password",
            headers=admin,
            json={"new_password": PROVISIONAL},
        )
        assert reset.status_code == 204
        await login(http, tech_email, CHOSEN, expected=401)
        tech = await login(http, tech_email, PROVISIONAL)
        assert (await http.get("/api/v1/field/bootstrap", headers=tech)).status_code == 403

        own = await http.post(
            f"/api/v1/team/{admin_membership_id}/reset-password",
            headers=admin,
            json={"new_password": PROVISIONAL},
        )
        assert own.status_code == 409
        other_tenant_member = await http.post(
            f"/api/v1/team/{outsider_membership_id}/reset-password",
            headers=admin,
            json={"new_password": PROVISIONAL},
        )
        assert other_tenant_member.status_code == 404

        # Perfil: troca entre perfis internos; portal e equipe nao se misturam.
        promoted = await http.patch(
            f"/api/v1/team/{tech_membership_id}", headers=admin, json={"role": "SUPERVISOR"}
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "SUPERVISOR"
        to_portal = await http.patch(
            f"/api/v1/team/{tech_membership_id}", headers=admin, json={"role": "CLIENTE"}
        )
        assert to_portal.status_code == 422
        assert to_portal.json()["detail"] == "client_role_is_fixed"
        from_portal = await http.patch(
            f"/api/v1/team/{by_email[portal_email]['membership_id']}",
            headers=admin,
            json={"role": "GESTOR"},
        )
        assert from_portal.status_code == 422
