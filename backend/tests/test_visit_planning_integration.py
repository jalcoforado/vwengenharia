from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import ChecklistTemplate
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Client, Development, Station


@pytest.mark.asyncio
async def test_recurring_visit_plan_generates_idempotent_agenda() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"plan-admin-{suffix}@example.com"
    tech_email = f"plan-tech-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"VW Plan {suffix}", slug=f"vw-plan-{suffix}")
        admin = User(
            email=admin_email,
            name="Gestor Planejamento",
            password_hash=hash_password(password),
        )
        tech = User(
            email=tech_email,
            name="Tecnico Planejamento",
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
            name=f"ETE Planejada {suffix}",
            code=f"PLAN-{suffix}",
            is_active=True,
        )
        template = ChecklistTemplate(
            tenant_id=tenant.id,
            name=f"Checklist {suffix}",
            version=1,
            is_active=True,
        )
        session.add_all([station, template])
        await session.commit()

        tech_membership_id = tech_membership.id
        station_id = station.id
        template_id = template.id

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

        start_at = (datetime.now(UTC) + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        created = await http.post(
            "/api/v1/visit-plans",
            headers=admin_headers,
            json={
                "station_id": str(station_id),
                "technician_membership_id": str(tech_membership_id),
                "checklist_template_id": str(template_id),
                "frequency_days": 7,
                "start_at": start_at.isoformat(),
                "notes": "Visita semanal programada",
            },
        )
        assert created.status_code == 201
        plan_id = created.json()["id"]
        assert datetime.fromisoformat(created.json()["next_due_at"]) == start_at

        first = await http.post(
            "/api/v1/visit-plans/generate",
            headers=admin_headers,
            json={"horizon_days": 30},
        )
        assert first.status_code == 200
        assert first.json()["generated"] == 5
        assert first.json()["plans_processed"] == 1

        second = await http.post(
            "/api/v1/visit-plans/generate",
            headers=admin_headers,
            json={"horizon_days": 30},
        )
        assert second.status_code == 200
        assert second.json()["generated"] == 0

        visits = await http.get(
            "/api/v1/visits?limit=100",
            headers=admin_headers,
        )
        assert visits.status_code == 200
        planned = [item for item in visits.json() if item["visit_plan_id"] == plan_id]
        assert len(planned) == 5
        assert all(item["status"] == "PROGRAMADA" for item in planned)

        tech_login = await http.post(
            "/api/v1/auth/login",
            json={"email": tech_email, "password": password},
        )
        assert tech_login.status_code == 200
        tech_headers = {
            "Authorization": f"Bearer {tech_login.json()['access_token']}"
        }
        tech_visits = await http.get(
            "/api/v1/visits?limit=100",
            headers=tech_headers,
        )
        assert tech_visits.status_code == 200
        assert {item["id"] for item in tech_visits.json()} == {
            item["id"] for item in planned
        }

        paused = await http.patch(
            f"/api/v1/visit-plans/{plan_id}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert paused.status_code == 200
        assert paused.json()["is_active"] is False
