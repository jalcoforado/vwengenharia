from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import Visit, VisitStatus
from app.models.identity import Membership, Role, Tenant, User
from app.models.maintenance import Occurrence, OccurrenceStatus
from app.models.operations import Asset, AssetType, Client, Development, Station


@pytest.mark.asyncio
async def test_occurrence_work_order_sla_review_and_dashboard_flow() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"ops-admin-{suffix}@example.com"
    tech_email = f"ops-tech-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Ops {suffix}", slug=f"ops-{suffix}")
        admin = User(
            email=admin_email,
            name="Gestor Operacional",
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
            name=f"ETE {suffix}",
            code=f"OPS-{suffix}",
            is_active=True,
        )
        asset_type = AssetType(
            tenant_id=tenant.id,
            name=f"Aerador {suffix}",
            code=f"AER-{suffix}",
        )
        session.add_all([station, asset_type])
        await session.flush()
        asset = Asset(
            tenant_id=tenant.id,
            station_id=station.id,
            asset_type_id=asset_type.id,
            name="Aerador I",
            status="AGUARDANDO_MANUTENCAO",
        )
        visit = Visit(
            tenant_id=tenant.id,
            station_id=station.id,
            technician_membership_id=tech_membership.id,
            scheduled_for=datetime.now(UTC) - timedelta(hours=2),
            started_at=datetime.now(UTC) - timedelta(hours=1),
            finished_at=datetime.now(UTC),
            status=VisitStatus.AGUARDANDO_REVISAO.value,
        )
        session.add_all([asset, visit])
        await session.commit()

        tech_membership_id = tech_membership.id
        station_id = station.id
        asset_id = asset.id
        visit_id = visit.id

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

        tech_login = await http.post(
            "/api/v1/auth/login",
            json={"email": tech_email, "password": password},
        )
        assert tech_login.status_code == 200
        tech_headers = {
            "Authorization": f"Bearer {tech_login.json()['access_token']}"
        }

        occurrence = await http.post(
            "/api/v1/occurrences",
            headers=tech_headers,
            json={
                "visit_id": str(visit_id),
                "station_id": str(station_id),
                "asset_id": str(asset_id),
                "occurrence_type": "FALHA_AERADOR",
                "severity": "CRITICA",
                "description": "Aerador parado durante a visita.",
                "detected_at": datetime.now(UTC).isoformat(),
            },
        )
        assert occurrence.status_code == 201
        occurrence_id = occurrence.json()["id"]
        assert occurrence.json()["status"] == "ABERTA"

        work_order = await http.post(
            "/api/v1/work-orders",
            headers=admin_headers,
            json={
                "occurrence_id": occurrence_id,
                "assigned_membership_id": str(tech_membership_id),
                "priority": "CRITICA",
                "description": "Inspecionar e restabelecer o aerador.",
            },
        )
        assert work_order.status_code == 201
        work_order_id = work_order.json()["id"]
        assert work_order.json()["status"] == "ABERTA"
        due = datetime.fromisoformat(work_order.json()["sla_due_at"])
        assert due <= datetime.now(UTC) + timedelta(hours=8, minutes=1)

        invalid_transition = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=tech_headers,
            json={"status": "CONCLUIDA"},
        )
        assert invalid_transition.status_code == 409

        planned = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=admin_headers,
            json={"status": "PLANEJADA", "note": "Equipe acionada"},
        )
        assert planned.status_code == 200

        in_progress = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=tech_headers,
            json={"status": "EM_EXECUCAO", "note": "Tecnico no local"},
        )
        assert in_progress.status_code == 200
        assert in_progress.json()["started_at"] is not None

        completed = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=tech_headers,
            json={"status": "CONCLUIDA", "note": "Aerador restabelecido"},
        )
        assert completed.status_code == 200
        assert completed.json()["completed_at"] is not None

        tech_validate = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=tech_headers,
            json={"status": "VALIDADA"},
        )
        assert tech_validate.status_code == 403

        validated = await http.post(
            f"/api/v1/work-orders/{work_order_id}/transition",
            headers=admin_headers,
            json={"status": "VALIDADA", "note": "Servico conferido"},
        )
        assert validated.status_code == 200
        assert validated.json()["validated_at"] is not None

        history = await http.get(
            f"/api/v1/work-orders/{work_order_id}/history",
            headers=admin_headers,
        )
        assert history.status_code == 200
        assert [item["to_status"] for item in history.json()] == [
            "ABERTA",
            "PLANEJADA",
            "EM_EXECUCAO",
            "CONCLUIDA",
            "VALIDADA",
        ]

        review = await http.post(
            f"/api/v1/visits/{visit_id}/review",
            headers=admin_headers,
            json={"decision": "APROVAR", "notes": "Checklist e evidencias conferidos."},
        )
        assert review.status_code == 200
        assert review.json()["decision"] == "APROVAR"

        overview = await http.get("/api/v1/dashboard/overview", headers=admin_headers)
        assert overview.status_code == 200
        assert overview.json()["active_stations"] >= 1
        assert overview.json()["visits_waiting_review"] == 0

        sla = await http.get("/api/v1/dashboard/sla", headers=admin_headers)
        assert sla.status_code == 200
        assert {bucket["priority"] for bucket in sla.json()["buckets"]} == {
            "BAIXA",
            "MEDIA",
            "ALTA",
            "CRITICA",
        }

    async with session_factory() as session:
        resolved = await session.scalar(
            select(Occurrence).where(Occurrence.id == occurrence_id)
        )
        assert resolved is not None
        assert resolved.status == OccurrenceStatus.RESOLVIDA.value
