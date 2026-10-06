from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.audit import AuditEvent
from app.models.identity import Membership, Role, Tenant, User


@pytest.mark.asyncio
async def test_audit_events_are_tenant_scoped_and_role_protected() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"audit-admin-{suffix}@example.com"
    supervisor_email = f"audit-supervisor-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Audit A {suffix}", slug=f"audit-a-{suffix}")
        tenant_b = Tenant(name=f"Audit B {suffix}", slug=f"audit-b-{suffix}")
        admin = User(
            email=admin_email,
            name="Admin Auditoria",
            password_hash=hash_password(password),
        )
        supervisor = User(
            email=supervisor_email,
            name="Supervisor Auditoria",
            password_hash=hash_password(password),
        )
        session.add_all([tenant_a, tenant_b, admin, supervisor])
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
                    user_id=supervisor.id,
                    role=Role.SUPERVISOR.value,
                ),
            ]
        )
        session.add_all(
            [
                AuditEvent(
                    tenant_id=tenant_a.id,
                    actor_user_id=admin.id,
                    action="CLIENT_CREATE",
                    entity_type="client",
                    entity_id="a",
                    event_metadata={"fields": []},
                ),
                AuditEvent(
                    tenant_id=tenant_b.id,
                    actor_user_id=None,
                    action="CLIENT_CREATE",
                    entity_type="client",
                    entity_id="b",
                    event_metadata={"fields": []},
                ),
            ]
        )
        await session.commit()

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

        events = await http.get(
            "/api/v1/audit-events?action=CLIENT_CREATE",
            headers=admin_headers,
        )
        assert events.status_code == 200
        assert len(events.json()) == 1
        assert events.json()[0]["entity_id"] == "a"

        supervisor_login = await http.post(
            "/api/v1/auth/login",
            json={"email": supervisor_email, "password": password},
        )
        assert supervisor_login.status_code == 200
        supervisor_headers = {
            "Authorization": f"Bearer {supervisor_login.json()['access_token']}"
        }

        forbidden = await http.get(
            "/api/v1/audit-events",
            headers=supervisor_headers,
        )
        assert forbidden.status_code == 403
