from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Client, Development, Station


@pytest.mark.asyncio
async def test_field_visit_flow_is_offline_safe_and_tenant_scoped() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    manager_email = f"manager-field-{suffix}@example.com"
    tech_email = f"tech-field-{suffix}@example.com"
    other_tech_email = f"tech-other-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Campo A {suffix}", slug=f"campo-a-{suffix}")
        tenant_b = Tenant(name=f"Campo B {suffix}", slug=f"campo-b-{suffix}")
        manager = User(
            email=manager_email,
            name="Gestor Campo",
            password_hash=hash_password(password),
        )
        technician = User(
            email=tech_email,
            name="Tecnico Campo",
            password_hash=hash_password(password),
        )
        other_technician = User(
            email=other_tech_email,
            name="Outro Tecnico",
            password_hash=hash_password(password),
        )
        session.add_all([tenant_a, tenant_b, manager, technician, other_technician])
        await session.flush()
        session.add_all(
            [
                Membership(
                    tenant_id=tenant_a.id,
                    user_id=manager.id,
                    role=Role.GESTOR.value,
                ),
                Membership(
                    tenant_id=tenant_a.id,
                    user_id=technician.id,
                    role=Role.TECNICO.value,
                ),
                Membership(
                    tenant_id=tenant_a.id,
                    user_id=other_technician.id,
                    role=Role.TECNICO.value,
                ),
            ]
        )

        client_a = Client(tenant_id=tenant_a.id, name=f"Cliente A {suffix}")
        client_b = Client(tenant_id=tenant_b.id, name=f"Cliente B {suffix}")
        session.add_all([client_a, client_b])
        await session.flush()
        development_a = Development(
            tenant_id=tenant_a.id,
            client_id=client_a.id,
            name=f"Empreendimento A {suffix}",
        )
        development_b = Development(
            tenant_id=tenant_b.id,
            client_id=client_b.id,
            name=f"Empreendimento B {suffix}",
        )
        session.add_all([development_a, development_b])
        await session.flush()
        station_a = Station(
            tenant_id=tenant_a.id,
            development_id=development_a.id,
            name=f"ETE A {suffix}",
        )
        station_b = Station(
            tenant_id=tenant_b.id,
            development_id=development_b.id,
            name=f"ETE B {suffix}",
        )
        session.add_all([station_a, station_b])
        await session.commit()

        technician_id = technician.id
        other_technician_id = other_technician.id
        station_a_id = station_a.id
        station_b_id = station_b.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        manager_login = await http.post(
            "/api/v1/auth/login",
            json={"email": manager_email, "password": password},
        )
        assert manager_login.status_code == 200
        manager_headers = {
            "Authorization": f"Bearer {manager_login.json()['access_token']}"
        }

        template = await http.post(
            "/api/v1/checklist-templates",
            headers=manager_headers,
            json={
                "name": f"Checklist ETE {suffix}",
                "station_type": "ETE",
                "version": 1,
                "items": [
                    {
                        "code": "GRADE",
                        "label": "Grade limpa?",
                        "item_type": "BOOLEAN",
                        "required": True,
                        "sort_order": 10,
                    },
                    {
                        "code": "AERADOR",
                        "label": "Situacao do aerador",
                        "item_type": "ASSET_STATUS",
                        "required": False,
                        "sort_order": 20,
                    },
                ],
            },
        )
        assert template.status_code == 201
        template_id = template.json()["id"]

        detail = await http.get(
            f"/api/v1/checklist-templates/{template_id}",
            headers=manager_headers,
        )
        assert detail.status_code == 200
        required_item_id = next(
            item["id"] for item in detail.json()["items"] if item["code"] == "GRADE"
        )

        foreign_station = await http.post(
            "/api/v1/visits",
            headers=manager_headers,
            json={
                "station_id": str(station_b_id),
                "assigned_user_id": str(technician_id),
                "checklist_template_id": template_id,
                "scheduled_for": datetime.now(UTC).isoformat(),
            },
        )
        assert foreign_station.status_code == 404

        visit = await http.post(
            "/api/v1/visits",
            headers=manager_headers,
            json={
                "station_id": str(station_a_id),
                "assigned_user_id": str(technician_id),
                "checklist_template_id": template_id,
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        assert visit.status_code == 201
        visit_id = visit.json()["id"]

        other_visit = await http.post(
            "/api/v1/visits",
            headers=manager_headers,
            json={
                "station_id": str(station_a_id),
                "assigned_user_id": str(other_technician_id),
                "checklist_template_id": template_id,
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            },
        )
        assert other_visit.status_code == 201

        tech_login = await http.post(
            "/api/v1/auth/login",
            json={"email": tech_email, "password": password},
        )
        assert tech_login.status_code == 200
        tech_headers = {"Authorization": f"Bearer {tech_login.json()['access_token']}"}

        agenda = await http.get("/api/v1/visits", headers=tech_headers)
        assert agenda.status_code == 200
        assert [item["id"] for item in agenda.json()] == [visit_id]

        hidden_other_visit = await http.get(
            f"/api/v1/visits/{other_visit.json()['id']}",
            headers=tech_headers,
        )
        assert hidden_other_visit.status_code == 404

        start_operation = str(uuid4())
        started = await http.post(
            f"/api/v1/visits/{visit_id}/start",
            headers=tech_headers,
            json={"client_operation_id": start_operation},
        )
        assert started.status_code == 200
        assert started.json()["status"] == "EM_EXECUCAO"

        replay_start = await http.post(
            f"/api/v1/visits/{visit_id}/start",
            headers=tech_headers,
            json={"client_operation_id": start_operation},
        )
        assert replay_start.status_code == 200
        assert replay_start.json()["started_at"] == started.json()["started_at"]

        incomplete = await http.post(
            f"/api/v1/visits/{visit_id}/finish",
            headers=tech_headers,
            json={"client_operation_id": str(uuid4())},
        )
        assert incomplete.status_code == 409
        assert incomplete.json()["detail"] == "required_checklist_incomplete"

        invalid_measurement = await http.post(
            f"/api/v1/visits/{visit_id}/measurements",
            headers=tech_headers,
            json={
                "client_operation_id": str(uuid4()),
                "measurements": [
                    {
                        "measurement_type": "PH",
                        "status": "NAO_MEDIDO",
                        "value": 0,
                        "unit": "pH",
                        "reason": "sem coleta",
                        "taken_at": datetime.now(UTC).isoformat(),
                    }
                ],
            },
        )
        assert invalid_measurement.status_code == 422

        measure_operation = str(uuid4())
        measurement = await http.post(
            f"/api/v1/visits/{visit_id}/measurements",
            headers=tech_headers,
            json={
                "client_operation_id": measure_operation,
                "measurements": [
                    {
                        "measurement_type": "PH",
                        "status": "MEDIDO",
                        "value": "7.2",
                        "unit": "pH",
                        "taken_at": datetime.now(UTC).isoformat(),
                    },
                    {
                        "measurement_type": "CL",
                        "status": "NAO_MEDIDO",
                        "reason": "sem reagente",
                        "taken_at": datetime.now(UTC).isoformat(),
                    },
                ],
            },
        )
        assert measurement.status_code == 200
        assert measurement.json()["duplicate"] is False

        replay_measurement = await http.post(
            f"/api/v1/visits/{visit_id}/measurements",
            headers=tech_headers,
            json={
                "client_operation_id": measure_operation,
                "measurements": [
                    {
                        "measurement_type": "PH",
                        "status": "MEDIDO",
                        "value": "9.9",
                        "unit": "pH",
                        "taken_at": datetime.now(UTC).isoformat(),
                    }
                ],
            },
        )
        assert replay_measurement.status_code == 200
        assert replay_measurement.json()["duplicate"] is True

        measurements = await http.get(
            f"/api/v1/visits/{visit_id}/measurements",
            headers=tech_headers,
        )
        assert measurements.status_code == 200
        assert len(measurements.json()) == 2
        ph = next(item for item in measurements.json() if item["measurement_type"] == "PH")
        assert float(ph["value"]) == 7.2

        answer_operation = str(uuid4())
        answers = await http.put(
            f"/api/v1/visits/{visit_id}/answers",
            headers=tech_headers,
            json={
                "client_operation_id": answer_operation,
                "answers": [
                    {
                        "item_id": required_item_id,
                        "value": {"value": True},
                        "note": "Grade limpa durante a visita",
                    }
                ],
            },
        )
        assert answers.status_code == 200
        assert answers.json()["duplicate"] is False

        replay_answers = await http.put(
            f"/api/v1/visits/{visit_id}/answers",
            headers=tech_headers,
            json={
                "client_operation_id": answer_operation,
                "answers": [
                    {
                        "item_id": required_item_id,
                        "value": {"value": False},
                    }
                ],
            },
        )
        assert replay_answers.status_code == 200
        assert replay_answers.json()["duplicate"] is True

        finish_operation = str(uuid4())
        finished = await http.post(
            f"/api/v1/visits/{visit_id}/finish",
            headers=tech_headers,
            json={
                "client_operation_id": finish_operation,
                "notes": "Visita concluida em campo",
            },
        )
        assert finished.status_code == 200
        assert finished.json()["status"] == "AGUARDANDO_REVISAO"
        assert finished.json()["finished_at"] is not None

        replay_finish = await http.post(
            f"/api/v1/visits/{visit_id}/finish",
            headers=tech_headers,
            json={
                "client_operation_id": finish_operation,
                "notes": "texto de replay que nao deve alterar",
            },
        )
        assert replay_finish.status_code == 200
        assert replay_finish.json()["notes"] == "Visita concluida em campo"
