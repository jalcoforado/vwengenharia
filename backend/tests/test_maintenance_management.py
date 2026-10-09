from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Asset, AssetType, Client, Development, Station


@pytest.mark.asyncio
async def test_preventive_maintenance_plan_and_execution_cycle() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"maintenance-admin-{suffix}@example.com"
    tech_email = f"maintenance-tech-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"MW Maint {suffix}", slug=f"vw-maint-{suffix}")
        admin = User(
            email=admin_email,
            name="Gestor Manutencao",
            password_hash=hash_password(password),
        )
        tech = User(
            email=tech_email,
            name="Tecnico Manutencao",
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
            role=Role.MANUTENCAO.value,
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
        asset_type = AssetType(
            tenant_id=tenant.id,
            name=f"Aerador {suffix}",
        )
        session.add_all([station, asset_type])
        await session.flush()
        asset = Asset(
            tenant_id=tenant.id,
            station_id=station.id,
            asset_type_id=asset_type.id,
            name="Aerador I",
            status="OPERANDO",
        )
        session.add(asset)
        await session.commit()
        asset_id = asset.id
        tech_membership_id = tech_membership.id

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

        first_due = datetime.now(UTC) + timedelta(days=2)
        created = await http.post(
            "/api/v1/maintenance/plans",
            headers=admin_headers,
            json={
                "asset_id": str(asset_id),
                "assigned_membership_id": str(tech_membership_id),
                "maintenance_type": "PREVENTIVA",
                "frequency_days": 30,
                "next_due_at": first_due.isoformat(),
                "instructions": "Limpar, lubrificar e inspecionar rolamentos.",
            },
        )
        assert created.status_code == 201
        plan_id = created.json()["id"]
        assert created.json()["frequency_days"] == 30

        tech_login = await http.post(
            "/api/v1/auth/login",
            json={"email": tech_email, "password": password},
        )
        assert tech_login.status_code == 200
        tech_headers = {
            "Authorization": f"Bearer {tech_login.json()['access_token']}"
        }

        plans = await http.get(
            "/api/v1/maintenance/plans",
            headers=tech_headers,
        )
        assert plans.status_code == 200
        assert [item["id"] for item in plans.json()] == [plan_id]

        started_at = datetime.now(UTC) - timedelta(hours=1)
        completed_at = datetime.now(UTC)
        execution = await http.post(
            "/api/v1/maintenance/executions",
            headers=tech_headers,
            json={
                "maintenance_plan_id": plan_id,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "notes": "Preventiva concluida sem anomalias.",
            },
        )
        assert execution.status_code == 201
        assert execution.json()["asset_id"] == str(asset_id)
        assert execution.json()["maintenance_type"] == "PREVENTIVA"

        refreshed = await http.get(
            "/api/v1/maintenance/plans",
            headers=admin_headers,
        )
        assert refreshed.status_code == 200
        plan = next(item for item in refreshed.json() if item["id"] == plan_id)
        assert datetime.fromisoformat(plan["last_completed_at"]) == completed_at
        assert datetime.fromisoformat(plan["next_due_at"]) == completed_at + timedelta(days=30)

        summary = await http.get(
            "/api/v1/maintenance/summary",
            headers=admin_headers,
        )
        assert summary.status_code == 200
        assert summary.json()["active_plans"] >= 1
        assert summary.json()["executions_last_30_days"] >= 1
