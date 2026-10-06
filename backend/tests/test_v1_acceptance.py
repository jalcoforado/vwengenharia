from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User


async def login(http: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_v1_complete_operational_journey() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"accept-admin-{suffix}@example.com"
    tech_email = f"accept-tech-{suffix}@example.com"
    maint_email = f"accept-maint-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"VW Acceptance {suffix}", slug=f"vw-accept-{suffix}")
        admin = User(
            email=admin_email,
            name="Gestor Acceptance",
            password_hash=hash_password(password),
        )
        tech = User(
            email=tech_email,
            name="Tecnico Acceptance",
            password_hash=hash_password(password),
        )
        maintenance = User(
            email=maint_email,
            name="Manutencao Acceptance",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, admin, tech, maintenance])
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
        maintenance_membership = Membership(
            tenant_id=tenant.id,
            user_id=maintenance.id,
            role=Role.MANUTENCAO.value,
        )
        session.add_all(
            [admin_membership, tech_membership, maintenance_membership]
        )
        await session.commit()

        tech_membership_id = tech_membership.id
        maintenance_membership_id = maintenance_membership.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        admin_headers = await login(http, admin_email, password)

        client = await http.post(
            "/api/v1/clients",
            headers=admin_headers,
            json={"name": f"Cliente Acceptance {suffix}"},
        )
        assert client.status_code == 201

        development = await http.post(
            "/api/v1/developments",
            headers=admin_headers,
            json={
                "client_id": client.json()["id"],
                "name": f"Condominio Acceptance {suffix}",
                "city": "Fortaleza",
                "state": "CE",
            },
        )
        assert development.status_code == 201

        station = await http.post(
            "/api/v1/stations",
            headers=admin_headers,
            json={
                "development_id": development.json()["id"],
                "name": f"ETE Acceptance {suffix}",
                "code": f"ACC-{suffix}",
                "station_type": "ETE",
                "visit_frequency_days": 7,
            },
        )
        assert station.status_code == 201
        station_id = station.json()["id"]

        asset_type = await http.post(
            "/api/v1/asset-types",
            headers=admin_headers,
            json={"name": f"Aerador Acceptance {suffix}", "code": f"AER-{suffix}"},
        )
        assert asset_type.status_code == 201

        asset = await http.post(
            "/api/v1/assets",
            headers=admin_headers,
            json={
                "station_id": station_id,
                "asset_type_id": asset_type.json()["id"],
                "name": "Aerador I",
                "status": "OPERANDO",
            },
        )
        assert asset.status_code == 201
        asset_id = asset.json()["id"]

        template = await http.post(
            "/api/v1/checklist-templates",
            headers=admin_headers,
            json={"name": f"Checklist Acceptance {suffix}", "version": 1},
        )
        assert template.status_code == 201
        template_id = template.json()["id"]

        checklist_item = await http.post(
            f"/api/v1/checklist-templates/{template_id}/items",
            headers=admin_headers,
            json={
                "code": "GRADE_LIMPA",
                "label": "Grade limpa?",
                "answer_type": "BOOLEAN",
                "required": True,
                "position": 10,
            },
        )
        assert checklist_item.status_code == 201
        item_id = checklist_item.json()["id"]

        plan_start = (datetime.now(UTC) + timedelta(minutes=1)).replace(
            microsecond=0
        )
        plan = await http.post(
            "/api/v1/visit-plans",
            headers=admin_headers,
            json={
                "station_id": station_id,
                "technician_membership_id": str(tech_membership_id),
                "checklist_template_id": template_id,
                "frequency_days": 7,
                "start_at": plan_start.isoformat(),
                "notes": "Plano de aceite v1",
            },
        )
        assert plan.status_code == 201

        generated = await http.post(
            "/api/v1/visit-plans/generate",
            headers=admin_headers,
            json={"horizon_days": 7},
        )
        assert generated.status_code == 200
        assert generated.json()["generated"] >= 1

        visits = await http.get("/api/v1/visits?limit=20", headers=admin_headers)
        assert visits.status_code == 200
        visit = next(
            item
            for item in visits.json()
            if item["visit_plan_id"] == plan.json()["id"]
        )
        visit_id = visit["id"]

        tech_headers = await login(http, tech_email, password)

        start = await http.post(
            f"/api/v1/visits/{visit_id}/start",
            headers=tech_headers,
            json={"client_operation_id": str(uuid4())},
        )
        assert start.status_code == 200
        assert start.json()["status"] == "EM_EXECUCAO"

        answer = await http.put(
            f"/api/v1/visits/{visit_id}/answers",
            headers=tech_headers,
            json={
                "item_id": item_id,
                "value": False,
                "client_operation_id": str(uuid4()),
            },
        )
        assert answer.status_code == 200

        measurement = await http.post(
            f"/api/v1/visits/{visit_id}/measurements",
            headers=tech_headers,
            json={
                "measurement_type": "PH",
                "status": "MEASURED",
                "value": "7.1",
                "unit": "pH",
                "measured_at": datetime.now(UTC).isoformat(),
                "client_operation_id": str(uuid4()),
            },
        )
        assert measurement.status_code == 201

        occurrence = await http.post(
            "/api/v1/occurrences",
            headers=tech_headers,
            json={
                "visit_id": visit_id,
                "station_id": station_id,
                "asset_id": asset_id,
                "occurrence_type": "FALHA_EQUIPAMENTO",
                "severity": "ALTA",
                "description": "Aerador apresentou ruido e parou durante a visita.",
                "detected_at": datetime.now(UTC).isoformat(),
            },
        )
        assert occurrence.status_code == 201
        occurrence_id = occurrence.json()["id"]

        material = await http.post(
            "/api/v1/material-requests",
            headers=tech_headers,
            json={
                "station_id": station_id,
                "visit_id": visit_id,
                "asset_id": asset_id,
                "category": "MATERIAL",
                "item_name": "Mangueira de reposicao",
                "quantity": "2",
                "unit": "m",
                "priority": "ALTA",
                "notes": "Necessaria para concluir o reparo.",
            },
        )
        assert material.status_code == 201
        material_id = material.json()["id"]

        finish = await http.post(
            f"/api/v1/visits/{visit_id}/finish",
            headers=tech_headers,
            json={"client_operation_id": str(uuid4())},
        )
        assert finish.status_code == 200
        assert finish.json()["status"] == "AGUARDANDO_REVISAO"

        work_order = await http.post(
            "/api/v1/work-orders",
            headers=admin_headers,
            json={
                "occurrence_id": occurrence_id,
                "assigned_membership_id": str(maintenance_membership_id),
                "priority": "ALTA",
                "description": "Inspecionar aerador e substituir mangueira.",
            },
        )
        assert work_order.status_code == 201
        work_order_id = work_order.json()["id"]

        approved_material = await http.patch(
            f"/api/v1/material-requests/{material_id}",
            headers=admin_headers,
            json={"status": "APROVADA"},
        )
        assert approved_material.status_code == 200

        buying_material = await http.patch(
            f"/api/v1/material-requests/{material_id}",
            headers=admin_headers,
            json={"status": "EM_COMPRA"},
        )
        assert buying_material.status_code == 200

        planned = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=admin_headers,
            json={"status": "PLANEJADA", "note": "Manutencao designada."},
        )
        assert planned.status_code == 200

        maintenance_headers = await login(http, maint_email, password)

        in_progress = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=maintenance_headers,
            json={"status": "EM_EXECUCAO", "note": "Equipe no local."},
        )
        assert in_progress.status_code == 200

        execution = await http.post(
            "/api/v1/maintenance/executions",
            headers=maintenance_headers,
            json={
                "work_order_id": work_order_id,
                "asset_id": asset_id,
                "maintenance_type": "CORRETIVA",
                "started_at": (datetime.now(UTC) - timedelta(minutes=30)).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "notes": "Mangueira substituida e aerador testado.",
            },
        )
        assert execution.status_code == 201

        completed = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=maintenance_headers,
            json={"status": "CONCLUIDA", "note": "Equipamento normalizado."},
        )
        assert completed.status_code == 200

        fulfilled_material = await http.patch(
            f"/api/v1/material-requests/{material_id}",
            headers=admin_headers,
            json={"status": "ATENDIDA", "notes": "Material aplicado na manutencao."},
        )
        assert fulfilled_material.status_code == 200

        validated = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=admin_headers,
            json={"status": "VALIDADA", "note": "Servico validado."},
        )
        assert validated.status_code == 200

        review = await http.post(
            f"/api/v1/visits/{visit_id}/review",
            headers=admin_headers,
            json={"decision": "APROVAR", "notes": "Visita conferida."},
        )
        assert review.status_code == 200

        station_view = await http.get(
            f"/api/v1/stations/{station_id}/overview",
            headers=admin_headers,
        )
        assert station_view.status_code == 200
        assert station_view.json()["summary"]["open_work_orders"] == 0
        assert station_view.json()["summary"]["open_material_requests"] == 0

        audits = await http.get(
            "/api/v1/audit-events?limit=500",
            headers=admin_headers,
        )
        assert audits.status_code == 200
        actions = {item["action"] for item in audits.json()}
        assert "MATERIAL_REQUEST_CREATE" in actions
        assert "MATERIAL_REQUEST_UPDATE" in actions

        integration_key = await http.post(
            "/api/v1/integration-keys",
            headers=admin_headers,
            json={"name": f"iAnalisys Acceptance {suffix}"},
        )
        assert integration_key.status_code == 201
        integration_headers = {
            "X-Integration-Key": integration_key.json()["secret"]
        }

        exported_visits = await http.get(
            "/api/v1/integration/v1/visits",
            headers=integration_headers,
        )
        assert exported_visits.status_code == 200
        assert any(item["id"] == visit_id for item in exported_visits.json()["items"])

        exported_orders = await http.get(
            "/api/v1/integration/v1/work-orders",
            headers=integration_headers,
        )
        assert exported_orders.status_code == 200
        assert any(
            item["id"] == work_order_id
            for item in exported_orders.json()["items"]
        )


@pytest.mark.asyncio
async def test_v1_rbac_blocks_field_user_from_management_surfaces() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    email = f"rbac-tech-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"RBAC {suffix}", slug=f"rbac-{suffix}")
        user = User(
            email=email,
            name="Tecnico RBAC",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, user])
        await session.flush()
        session.add(
            Membership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=Role.TECNICO.value,
            )
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        headers = await login(http, email, password)

        for method, path, payload in [
            ("GET", "/api/v1/audit-events", None),
            ("GET", "/api/v1/integration-keys", None),
            ("GET", "/api/v1/legacy-migration/summary", None),
            ("POST", "/api/v1/clients", {"name": "Nao permitido"}),
        ]:
            response = await http.request(
                method,
                path,
                headers=headers,
                json=payload,
            )
            assert response.status_code == 403, (method, path, response.text)
