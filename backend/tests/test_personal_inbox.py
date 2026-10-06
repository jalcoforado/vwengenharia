from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import Visit
from app.models.identity import Membership, Role, Tenant, User
from app.models.maintenance import MaintenancePlan, WorkOrder
from app.models.operations import Asset, AssetType, Client, Development, Station


@pytest.mark.asyncio
async def test_personal_inbox_separates_field_and_management_tasks() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"inbox-admin-{suffix}@example.com"
    tech_email = f"inbox-tech-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Inbox {suffix}", slug=f"inbox-{suffix}")
        admin = User(
            email=admin_email,
            name="Gestor",
            password_hash=hash_password(password),
        )
        tech = User(
            email=tech_email,
            name="Tecnico",
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
        asset_type = AssetType(tenant_id=tenant.id, name=f"Tipo {suffix}")
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
        await session.flush()

        visit = Visit(
            tenant_id=tenant.id,
            station_id=station.id,
            technician_membership_id=tech_membership.id,
            scheduled_for=datetime.now(UTC) - timedelta(hours=2),
            status="PROGRAMADA",
        )
        review_visit = Visit(
            tenant_id=tenant.id,
            station_id=station.id,
            technician_membership_id=tech_membership.id,
            scheduled_for=datetime.now(UTC) - timedelta(days=1),
            finished_at=datetime.now(UTC),
            status="AGUARDANDO_REVISAO",
        )
        order = WorkOrder(
            tenant_id=tenant.id,
            station_id=station.id,
            asset_id=asset.id,
            assigned_membership_id=tech_membership.id,
            priority="CRITICA",
            status="PLANEJADA",
            description="Restabelecer aerador.",
            sla_due_at=datetime.now(UTC) + timedelta(hours=2),
        )
        maintenance = MaintenancePlan(
            tenant_id=tenant.id,
            asset_id=asset.id,
            assigned_membership_id=tech_membership.id,
            maintenance_type="PREVENTIVA",
            frequency_days=30,
            next_due_at=datetime.now(UTC) - timedelta(days=1),
            is_active=True,
        )
        session.add_all([visit, review_visit, order, maintenance])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        tech_login = await http.post(
            "/api/v1/auth/login",
            json={"email": tech_email, "password": password},
        )
        tech_headers = {
            "Authorization": f"Bearer {tech_login.json()['access_token']}"
        }
        tech_inbox = await http.get("/api/v1/inbox", headers=tech_headers)
        assert tech_inbox.status_code == 200
        tech_kinds = {item["kind"] for item in tech_inbox.json()}
        assert {"VISIT", "WORK_ORDER", "MAINTENANCE"} <= tech_kinds
        assert "VISIT_REVIEW" not in tech_kinds

        admin_login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": password},
        )
        admin_headers = {
            "Authorization": f"Bearer {admin_login.json()['access_token']}"
        }
        admin_inbox = await http.get("/api/v1/inbox", headers=admin_headers)
        assert admin_inbox.status_code == 200
        admin_kinds = {item["kind"] for item in admin_inbox.json()}
        assert "VISIT_REVIEW" in admin_kinds
        assert "WORK_ORDER_MANAGEMENT" in admin_kinds
        assert "MAINTENANCE_MANAGEMENT" in admin_kinds
