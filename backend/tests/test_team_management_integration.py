from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User


@pytest.mark.asyncio
async def test_team_management_and_password_change() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    new_password = "senha-nova-segura-456"
    admin_email = f"team-admin-{suffix}@example.com"
    supervisor_email = f"team-supervisor-{suffix}@example.com"
    tech_email = f"team-tech-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"MW Team {suffix}", slug=f"mw-team-{suffix}")
        admin = User(
            email=admin_email,
            name="Administrador",
            password_hash=hash_password(password),
        )
        supervisor = User(
            email=supervisor_email,
            name="Supervisor",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, admin, supervisor])
        await session.flush()
        admin_membership = Membership(
            tenant_id=tenant.id,
            user_id=admin.id,
            role=Role.ADMIN.value,
        )
        supervisor_membership = Membership(
            tenant_id=tenant.id,
            user_id=supervisor.id,
            role=Role.SUPERVISOR.value,
        )
        session.add_all([admin_membership, supervisor_membership])
        await session.commit()
        admin_membership_id = admin_membership.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        admin_login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": password},
        )
        assert admin_login.status_code == 200
        admin_headers = {
            "Authorization": f"Bearer {admin_login.json()['access_token']}"
        }

        created = await http.post(
            "/api/v1/team",
            headers=admin_headers,
            json={
                "email": tech_email,
                "name": "Tecnico Novo",
                "password": password,
                "role": "TECNICO",
            },
        )
        assert created.status_code == 201
        tech_membership_id = created.json()["membership_id"]
        assert created.json()["role"] == "TECNICO"
        assert created.json()["is_active"] is True

        listed = await http.get(
            "/api/v1/team?active_only=true&roles=TECNICO",
            headers=admin_headers,
        )
        assert listed.status_code == 200
        assert [item["email"] for item in listed.json()] == [tech_email]

        promoted = await http.patch(
            f"/api/v1/team/{tech_membership_id}",
            headers=admin_headers,
            json={"role": "MANUTENCAO"},
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "MANUTENCAO"

        self_change = await http.patch(
            f"/api/v1/team/{admin_membership_id}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert self_change.status_code == 409
        assert self_change.json()["detail"] == "cannot_change_own_membership"

        forbidden_superadmin = await http.post(
            "/api/v1/team",
            headers=admin_headers,
            json={
                "email": f"super-{suffix}@example.com",
                "name": "Super Admin",
                "password": password,
                "role": "SUPERADMIN",
            },
        )
        assert forbidden_superadmin.status_code == 403

        supervisor_login = await http.post(
            "/api/v1/auth/login",
            json={"email": supervisor_email, "password": password},
        )
        assert supervisor_login.status_code == 200
        supervisor_headers = {
            "Authorization": f"Bearer {supervisor_login.json()['access_token']}"
        }

        supervisor_list = await http.get("/api/v1/team", headers=supervisor_headers)
        assert supervisor_list.status_code == 200

        supervisor_create = await http.post(
            "/api/v1/team",
            headers=supervisor_headers,
            json={
                "email": f"blocked-{suffix}@example.com",
                "name": "Bloqueado",
                "password": password,
                "role": "TECNICO",
            },
        )
        assert supervisor_create.status_code == 403

        change = await http.post(
            "/api/v1/auth/change-password",
            headers=admin_headers,
            json={
                "current_password": password,
                "new_password": new_password,
            },
        )
        assert change.status_code == 204

        old_login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": password},
        )
        assert old_login.status_code == 401

        new_login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": new_password},
        )
        assert new_login.status_code == 200
