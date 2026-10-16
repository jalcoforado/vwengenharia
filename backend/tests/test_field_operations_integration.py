from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User


@pytest.mark.asyncio
async def test_field_flow_is_offline_safe_and_scoped_to_assigned_technician() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"field-admin-{suffix}@example.com"
    tech_email = f"field-tech-{suffix}@example.com"
    other_tech_email = f"field-other-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"MW Field {suffix}", slug=f"mw-field-{suffix}")
        admin = User(
            email=admin_email,
            name="Supervisor Campo",
            password_hash=hash_password(password),
        )
        tech = User(
            email=tech_email,
            name="Tecnico Campo",
            password_hash=hash_password(password),
        )
        other_tech = User(
            email=other_tech_email,
            name="Outro Tecnico",
            password_hash=hash_password(password),
        )
        session.add_all([tenant, admin, tech, other_tech])
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
        other_membership = Membership(
            tenant_id=tenant.id,
            user_id=other_tech.id,
            role=Role.TECNICO.value,
        )
        session.add_all([admin_membership, tech_membership, other_membership])
        await session.commit()
        tech_membership_id = tech_membership.id
        other_membership_id = other_membership.id

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

        client = await http.post(
            "/api/v1/clients",
            headers=admin_headers,
            json={"name": f"Cliente Field {suffix}"},
        )
        assert client.status_code == 201

        development = await http.post(
            "/api/v1/developments",
            headers=admin_headers,
            json={
                "client_id": client.json()["id"],
                "name": f"Empreendimento Field {suffix}",
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
                "name": f"ETE Field {suffix}",
                "code": f"FIELD-{suffix}",
                "visit_frequency_days": 7,
            },
        )
        assert station.status_code == 201
        station_id = station.json()["id"]

        template = await http.post(
            "/api/v1/checklist-templates",
            headers=admin_headers,
            json={"name": f"Checklist ETE {suffix}", "version": 1},
        )
        assert template.status_code == 201
        template_id = template.json()["id"]

        required_item = await http.post(
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
        assert required_item.status_code == 201
        required_item_id = required_item.json()["id"]

        scheduled_for = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        create_op = str(uuid4())
        visit = await http.post(
            "/api/v1/visits",
            headers=admin_headers,
            json={
                "station_id": station_id,
                "technician_membership_id": str(tech_membership_id),
                "checklist_template_id": template_id,
                "scheduled_for": scheduled_for,
                "client_operation_id": create_op,
            },
        )
        assert visit.status_code == 201
        visit_id = visit.json()["id"]

        duplicate_visit = await http.post(
            "/api/v1/visits",
            headers=admin_headers,
            json={
                "station_id": station_id,
                "technician_membership_id": str(tech_membership_id),
                "checklist_template_id": template_id,
                "scheduled_for": scheduled_for,
                "client_operation_id": create_op,
            },
        )
        assert duplicate_visit.status_code == 201
        assert duplicate_visit.json()["id"] == visit_id

        other_visit = await http.post(
            "/api/v1/visits",
            headers=admin_headers,
            json={
                "station_id": station_id,
                "technician_membership_id": str(other_membership_id),
                "checklist_template_id": template_id,
                "scheduled_for": scheduled_for,
                "client_operation_id": str(uuid4()),
            },
        )
        assert other_visit.status_code == 201

        tech_login = await http.post(
            "/api/v1/auth/login",
            json={"email": tech_email, "password": password},
        )
        assert tech_login.status_code == 200
        tech_headers = {
            "Authorization": f"Bearer {tech_login.json()['access_token']}"
        }

        bootstrap = await http.get("/api/v1/field/bootstrap", headers=tech_headers)
        assert bootstrap.status_code == 200
        bootstrap_ids = {item["id"] for item in bootstrap.json()["visits"]}
        assert visit_id in bootstrap_ids
        assert other_visit.json()["id"] not in bootstrap_ids

        forbidden_other = await http.post(
            f"/api/v1/visits/{other_visit.json()['id']}/start",
            headers=tech_headers,
            json={"client_operation_id": str(uuid4())},
        )
        assert forbidden_other.status_code == 404

        start_op = str(uuid4())
        started = await http.post(
            f"/api/v1/visits/{visit_id}/start",
            headers=tech_headers,
            json={"client_operation_id": start_op},
        )
        assert started.status_code == 200
        assert started.json()["status"] == "EM_EXECUCAO"

        replay_start = await http.post(
            f"/api/v1/visits/{visit_id}/start",
            headers=tech_headers,
            json={"client_operation_id": start_op},
        )
        assert replay_start.status_code == 200
        assert replay_start.json()["id"] == visit_id

        invalid_measurement = await http.post(
            f"/api/v1/visits/{visit_id}/measurements",
            headers=tech_headers,
            json={
                "measurement_type": "PH",
                "status": "NOT_MEASURED",
                "value": 0,
                "reason": "sem coleta",
                "measured_at": datetime.now(UTC).isoformat(),
            },
        )
        assert invalid_measurement.status_code == 422

        measurement_op = str(uuid4())
        measurement = await http.post(
            f"/api/v1/visits/{visit_id}/measurements",
            headers=tech_headers,
            json={
                "measurement_type": "PH",
                "status": "MEASURED",
                "value": "7.20",
                "unit": "pH",
                "measured_at": datetime.now(UTC).isoformat(),
                "client_operation_id": measurement_op,
            },
        )
        assert measurement.status_code == 201
        measurement_id = measurement.json()["id"]

        replay_measurement = await http.post(
            f"/api/v1/visits/{visit_id}/measurements",
            headers=tech_headers,
            json={
                "measurement_type": "PH",
                "status": "MEASURED",
                "value": "7.20",
                "unit": "pH",
                "measured_at": datetime.now(UTC).isoformat(),
                "client_operation_id": measurement_op,
            },
        )
        assert replay_measurement.status_code == 201
        assert replay_measurement.json()["id"] == measurement_id

        finish_without_required = await http.post(
            f"/api/v1/visits/{visit_id}/finish",
            headers=tech_headers,
            json={"client_operation_id": str(uuid4())},
        )
        assert finish_without_required.status_code == 422
        assert (
            finish_without_required.json()["detail"]["code"]
            == "required_answers_missing"
        )

        answer_op = str(uuid4())
        answer = await http.put(
            f"/api/v1/visits/{visit_id}/answers",
            headers=tech_headers,
            json={
                "item_id": required_item_id,
                "value": True,
                "client_operation_id": answer_op,
            },
        )
        assert answer.status_code == 200

        finish_op = str(uuid4())
        finished = await http.post(
            f"/api/v1/visits/{visit_id}/finish",
            headers=tech_headers,
            json={"client_operation_id": finish_op},
        )
        assert finished.status_code == 200
        assert finished.json()["status"] == "AGUARDANDO_REVISAO"
        assert finished.json()["finished_at"] is not None

        replay_finish = await http.post(
            f"/api/v1/visits/{visit_id}/finish",
            headers=tech_headers,
            json={"client_operation_id": finish_op},
        )
        assert replay_finish.status_code == 200
        assert replay_finish.json()["status"] == "AGUARDANDO_REVISAO"

        synced = await http.get("/api/v1/field/bootstrap", headers=tech_headers)
        assert synced.status_code == 200
        assert any(item["id"] == answer.json()["id"] for item in synced.json()["answers"])
        assert any(
            item["id"] == measurement_id for item in synced.json()["measurements"]
        )
