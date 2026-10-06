from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import Visit
from app.models.identity import Membership, Role, Tenant, User
from app.models.maintenance import (
    MaintenancePlan,
    Occurrence,
    WorkOrder,
)
from app.models.materials import MaterialRequest
from app.models.operations import Asset, AssetType, Client, Development, Station


@pytest.mark.asyncio
async def test_station_overview_aggregates_only_selected_station() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    email = f"station-overview-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"VW {suffix}", slug=f"vw-overview-{suffix}")
        user = User(
            email=email,
            name="Gestor",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, user])
        await session.flush()
        membership = Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=Role.ADMIN.value,
        )
        session.add(membership)
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
            name=f"ETE Principal {suffix}",
            is_active=True,
        )
        other_station = Station(
            tenant_id=tenant.id,
            development_id=development.id,
            name=f"ETE Outra {suffix}",
            is_active=True,
        )
        asset_type = AssetType(tenant_id=tenant.id, name=f"Aerador {suffix}")
        session.add_all([station, other_station, asset_type])
        await session.flush()

        asset = Asset(
            tenant_id=tenant.id,
            station_id=station.id,
            asset_type_id=asset_type.id,
            name="Aerador I",
            status="AGUARDANDO_MANUTENCAO",
            is_active=True,
        )
        other_asset = Asset(
            tenant_id=tenant.id,
            station_id=other_station.id,
            asset_type_id=asset_type.id,
            name="Aerador Outra",
            status="OPERANDO",
            is_active=True,
        )
        session.add_all([asset, other_asset])
        await session.flush()

        visit = Visit(
            tenant_id=tenant.id,
            station_id=station.id,
            technician_membership_id=membership.id,
            scheduled_for=datetime.now(UTC) - timedelta(days=1),
            status="AGUARDANDO_REVISAO",
        )
        session.add(visit)
        await session.flush()

        occurrence = Occurrence(
            tenant_id=tenant.id,
            visit_id=visit.id,
            station_id=station.id,
            asset_id=asset.id,
            occurrence_type="FALHA_AERADOR",
            severity="ALTA",
            status="ABERTA",
            description="Aerador parado.",
            detected_at=datetime.now(UTC),
            created_by_user_id=user.id,
        )
        session.add(occurrence)
        await session.flush()

        work_order = WorkOrder(
            tenant_id=tenant.id,
            occurrence_id=occurrence.id,
            station_id=station.id,
            asset_id=asset.id,
            assigned_membership_id=membership.id,
            priority="ALTA",
            status="PLANEJADA",
            description="Restabelecer aerador.",
            sla_due_at=datetime.now(UTC) - timedelta(hours=1),
        )
        maintenance = MaintenancePlan(
            tenant_id=tenant.id,
            asset_id=asset.id,
            assigned_membership_id=membership.id,
            maintenance_type="PREVENTIVA",
            frequency_days=30,
            next_due_at=datetime.now(UTC) - timedelta(days=2),
            instructions="Inspecionar aerador.",
            is_active=True,
        )
        material = MaterialRequest(
            tenant_id=tenant.id,
            station_id=station.id,
            visit_id=visit.id,
            asset_id=asset.id,
            requested_by_user_id=user.id,
            category="MATERIAL",
            item_name="Pastilha de cloro",
            quantity=2,
            unit="un",
            priority="MEDIA",
            status="SOLICITADA",
        )
        session.add_all([work_order, maintenance, material])
        await session.commit()
        station_id = station.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = await http.get(
            f"/api/v1/stations/{station_id}/overview",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["station"]["id"] == str(station_id)
        assert [item["name"] for item in body["assets"]] == ["Aerador I"]
        assert len(body["visits"]) == 1
        assert len(body["occurrences"]) == 1
        assert len(body["work_orders"]) == 1
        assert len(body["maintenance_plans"]) == 1
        assert len(body["material_requests"]) == 1

        summary = body["summary"]
        assert summary["active_assets"] == 1
        assert summary["unavailable_assets"] == 1
        assert summary["open_occurrences"] == 1
        assert summary["open_work_orders"] == 1
        assert summary["overdue_work_orders"] == 1
        assert summary["overdue_maintenance"] == 1
        assert summary["open_material_requests"] == 1
