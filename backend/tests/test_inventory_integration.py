from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import Visit
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Client, Development, Station


async def login(http: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_inventory_ledger_and_material_request_issue() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"stock-admin-{suffix}@example.com"
    tech_email = f"stock-tech-{suffix}@example.com"
    other_admin_email = f"stock-other-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Stock {suffix}", slug=f"stock-{suffix}")
        other_tenant = Tenant(
            name=f"Other Stock {suffix}",
            slug=f"other-stock-{suffix}",
        )
        admin = User(
            email=admin_email,
            name="Gestor Estoque",
            password_hash=hash_password(password),
        )
        tech = User(
            email=tech_email,
            name="Tecnico Estoque",
            password_hash=hash_password(password),
        )
        other_admin = User(
            email=other_admin_email,
            name="Outro Gestor",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, other_tenant, admin, tech, other_admin])
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
        other_admin_membership = Membership(
            tenant_id=other_tenant.id,
            user_id=other_admin.id,
            role=Role.ADMIN.value,
        )
        session.add_all(
            [admin_membership, tech_membership, other_admin_membership]
        )
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
        session.add(station)
        await session.flush()
        visit = Visit(
            tenant_id=tenant.id,
            station_id=station.id,
            technician_membership_id=tech_membership.id,
            scheduled_for=datetime.now(UTC),
            status="EM_EXECUCAO",
        )
        session.add(visit)
        await session.commit()
        station_id = station.id
        visit_id = visit.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        admin_headers = await login(http, admin_email, password)
        tech_headers = await login(http, tech_email, password)
        other_headers = await login(http, other_admin_email, password)

        item_response = await http.post(
            "/api/v1/inventory/items",
            headers=admin_headers,
            json={
                "code": "CLORO-PAST",
                "name": "Pastilha de cloro",
                "unit": "un",
                "minimum_quantity": "9",
            },
        )
        assert item_response.status_code == 201
        item_id = item_response.json()["id"]
        assert item_response.json()["current_quantity"] == "0.000"

        entry = await http.post(
            "/api/v1/inventory/movements",
            headers=admin_headers,
            json={
                "inventory_item_id": item_id,
                "movement_type": "ENTRADA",
                "quantity": "10",
                "unit_cost": "4.50",
                "occurred_at": datetime.now(UTC).isoformat(),
                "notes": "Entrada inicial.",
            },
        )
        assert entry.status_code == 201
        assert entry.json()["balance_after"] == "10.000"

        request = await http.post(
            "/api/v1/material-requests",
            headers=tech_headers,
            json={
                "station_id": str(station_id),
                "visit_id": str(visit_id),
                "inventory_item_id": item_id,
                "category": "MATERIAL",
                "item_name": "Pastilha de cloro",
                "quantity": "2",
                "unit": "un",
                "priority": "ALTA",
            },
        )
        assert request.status_code == 201
        request_id = request.json()["id"]

        issue = await http.post(
            f"/api/v1/material-requests/{request_id}/issue",
            headers=admin_headers,
            json={
                "inventory_item_id": item_id,
                "notes": "Entregue ao tecnico.",
            },
        )
        assert issue.status_code == 200
        assert issue.json()["movement_type"] == "SAIDA"
        assert issue.json()["quantity"] == "2.000"
        assert issue.json()["balance_after"] == "8.000"
        assert issue.json()["material_request_id"] == request_id

        requests = await http.get(
            "/api/v1/material-requests",
            headers=admin_headers,
        )
        assert requests.status_code == 200
        stored_request = next(
            item for item in requests.json() if item["id"] == request_id
        )
        assert stored_request["status"] == "ATENDIDA"
        assert stored_request["inventory_item_id"] == item_id

        insufficient = await http.post(
            "/api/v1/inventory/movements",
            headers=admin_headers,
            json={
                "inventory_item_id": item_id,
                "movement_type": "SAIDA",
                "quantity": "9",
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )
        assert insufficient.status_code == 409
        assert insufficient.json()["detail"] == "insufficient_inventory"

        summary = await http.get(
            "/api/v1/inventory/summary",
            headers=admin_headers,
        )
        assert summary.status_code == 200
        assert summary.json()["active_items"] == 1
        assert summary.json()["low_stock_items"] == 1
        assert summary.json()["zero_stock_items"] == 0

        alerts = await http.get("/api/v1/alerts", headers=admin_headers)
        assert alerts.status_code == 200
        assert any(
            item["kind"] == "INVENTORY_LOW_STOCK"
            and item["entity_id"] == item_id
            for item in alerts.json()
        )

        inbox = await http.get("/api/v1/inbox", headers=admin_headers)
        assert inbox.status_code == 200
        assert any(
            item["kind"] == "INVENTORY_LOW_STOCK"
            and item["entity_id"] == item_id
            for item in inbox.json()
        )

        tech_movement = await http.post(
            "/api/v1/inventory/movements",
            headers=tech_headers,
            json={
                "inventory_item_id": item_id,
                "movement_type": "ENTRADA",
                "quantity": "1",
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )
        assert tech_movement.status_code == 403

        foreign_movement = await http.post(
            "/api/v1/inventory/movements",
            headers=other_headers,
            json={
                "inventory_item_id": item_id,
                "movement_type": "ENTRADA",
                "quantity": "1",
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )
        assert foreign_movement.status_code == 404

        items = await http.get(
            "/api/v1/inventory/items",
            headers=admin_headers,
        )
        assert items.status_code == 200
        stored_item = next(item for item in items.json() if item["id"] == item_id)
        assert stored_item["current_quantity"] == "8.000"
