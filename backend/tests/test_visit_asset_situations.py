from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import VisitAssetSituation
from app.models.identity import Membership, Role, Tenant, User


@pytest.mark.asyncio
async def test_asset_situation_is_recorded_per_visit_and_updates_asset_status() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    admin_email = f"situacao-admin-{suffix}@example.com"
    tech_email = f"situacao-tech-{suffix}@example.com"
    other_email = f"situacao-other-{suffix}@example.com"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Situacao {suffix}", slug=f"situacao-{suffix}")
        users = [
            User(email=email, name=name, password_hash=hash_password(password))
            for email, name in (
                (admin_email, "Admin"),
                (tech_email, "Tecnico Titular"),
                (other_email, "Outro Tecnico"),
            )
        ]
        session.add_all([tenant, *users])
        await session.flush()
        memberships = [
            Membership(tenant_id=tenant.id, user_id=user.id, role=role)
            for user, role in zip(
                users, (Role.ADMIN.value, Role.TECNICO.value, Role.TECNICO.value), strict=True
            )
        ]
        session.add_all(memberships)
        await session.commit()
        tenant_id = tenant.id
        tech_membership_id = str(memberships[1].id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:

        async def login(email: str) -> dict[str, str]:
            response = await http.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            )
            assert response.status_code == 200
            return {"Authorization": f"Bearer {response.json()['access_token']}"}

        admin = await login(admin_email)
        tech = await login(tech_email)
        other = await login(other_email)

        async def create(path: str, body: dict) -> dict:
            response = await http.post(path, headers=admin, json=body)
            assert response.status_code == 201, response.text
            return response.json()

        responsible = await create("/api/v1/clients", {"name": f"Sindica {suffix}"})
        development = await create(
            "/api/v1/developments",
            {"client_id": responsible["id"], "name": f"Condominio {suffix}"},
        )
        station = await create(
            "/api/v1/stations",
            {"development_id": development["id"], "name": f"ETE {suffix}", "code": f"S-{suffix}"},
        )
        other_station = await create(
            "/api/v1/stations",
            {"development_id": development["id"], "name": f"EEB {suffix}", "code": f"O-{suffix}"},
        )
        unit_type = await create("/api/v1/process-unit-types", {"name": f"Aeracao {suffix}"})
        unit = await create(
            "/api/v1/process-units",
            {"station_id": station["id"], "unit_type_id": unit_type["id"], "name": "Tanque 1"},
        )
        asset_type = await create("/api/v1/asset-types", {"name": f"Aerador {suffix}"})
        aerator = await create(
            "/api/v1/assets",
            {
                "station_id": station["id"],
                "asset_type_id": asset_type["id"],
                "process_unit_id": unit["id"],
                "name": "Aerador I",
            },
        )
        pump = await create(
            "/api/v1/assets",
            {"station_id": station["id"], "asset_type_id": asset_type["id"], "name": "Bomba I"},
        )
        foreign_asset = await create(
            "/api/v1/assets",
            {
                "station_id": other_station["id"],
                "asset_type_id": asset_type["id"],
                "name": "Bomba de outra estacao",
            },
        )
        visit = await create(
            "/api/v1/visits",
            {
                "station_id": station["id"],
                "technician_membership_id": tech_membership_id,
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        url = f"/api/v1/visits/{visit['id']}/asset-situations"

        not_started = await http.put(
            url, headers=tech, json={"asset_id": aerator["id"], "situation": "FUNCIONANDO"}
        )
        assert not_started.status_code == 409
        assert not_started.json()["detail"] == "visit_not_in_progress"

        started = await http.post(
            f"/api/v1/visits/{visit['id']}/start",
            headers=tech,
            json={"client_operation_id": str(uuid4())},
        )
        assert started.status_code == 200

        # O app do tecnico recebe unidades e equipamentos da estacao para montar a tela.
        bootstrap = (await http.get("/api/v1/field/bootstrap", headers=tech)).json()
        assert [item["name"] for item in bootstrap["units"]] == ["Tanque 1"]
        assert {
            (item["name"], item["process_unit_id"]) for item in bootstrap["assets"]
        } == {("Aerador I", unit["id"]), ("Bomba I", None)}
        assert bootstrap["asset_situations"] == []

        operation_id = str(uuid4())
        body = {
            "asset_id": aerator["id"],
            "situation": "NECESSARIO_VERIFICAR",
            "comment": "Ruido anormal",
            "client_operation_id": operation_id,
        }
        recorded = await http.put(url, headers=tech, json=body)
        assert recorded.status_code == 200
        assert recorded.json()["situation"] == "NECESSARIO_VERIFICAR"
        assert recorded.json()["comment"] == "Ruido anormal"

        # Reenvio da mesma operacao (app offline) devolve o mesmo registro.
        replayed = await http.put(url, headers=tech, json=body)
        assert replayed.status_code == 200
        assert replayed.json()["id"] == recorded.json()["id"]

        asset_after = await http.get(f"/api/v1/assets/{aerator['id']}", headers=admin)
        assert asset_after.json()["status"] == "NECESSITA_VERIFICACAO"

        # O tecnico corrige: continua sendo um unico registro por visita e equipamento.
        corrected = await http.put(
            url,
            headers=tech,
            json={
                "asset_id": aerator["id"],
                "situation": "FUNCIONANDO",
                "client_operation_id": str(uuid4()),
            },
        )
        assert corrected.status_code == 200
        assert corrected.json()["id"] == recorded.json()["id"]
        assert corrected.json()["comment"] is None
        asset_after = await http.get(f"/api/v1/assets/{aerator['id']}", headers=admin)
        assert asset_after.json()["status"] == "OPERANDO"

        other_without_comment = await http.put(
            url, headers=tech, json={"asset_id": pump["id"], "situation": "OUTRO"}
        )
        assert other_without_comment.status_code == 422

        other_situation = await http.put(
            url,
            headers=tech,
            json={"asset_id": pump["id"], "situation": "OUTRO", "comment": "Emprestada"},
        )
        assert other_situation.status_code == 200
        # "Outro" nao altera o status cadastrado do equipamento.
        pump_after = await http.get(f"/api/v1/assets/{pump['id']}", headers=admin)
        assert pump_after.json()["status"] == "OPERANDO"

        invalid = await http.put(
            url, headers=tech, json={"asset_id": pump["id"], "situation": "QUEBRADO"}
        )
        assert invalid.status_code == 422

        wrong_station = await http.put(
            url, headers=tech, json={"asset_id": foreign_asset["id"], "situation": "FUNCIONANDO"}
        )
        assert wrong_station.status_code == 404

        not_assigned = await http.put(
            url, headers=other, json={"asset_id": pump["id"], "situation": "FUNCIONANDO"}
        )
        assert not_assigned.status_code == 404

        bootstrap = (await http.get("/api/v1/field/bootstrap", headers=tech)).json()
        assert {
            (item["asset_id"], item["situation"]) for item in bootstrap["asset_situations"]
        } == {(aerator["id"], "FUNCIONANDO"), (pump["id"], "OUTRO")}

        report = await http.get(f"/api/v1/reports/visits/{visit['id']}.html", headers=admin)
        assert report.status_code == 200
        assert "Situação dos equipamentos" in report.text
        assert "Funcionando adequadamente" in report.text
        assert "Emprestada" in report.text

        key = await http.post(
            "/api/v1/integration-keys", headers=admin, json={"name": "iAnalisys"}
        )
        exported = await http.get(
            "/api/v1/integration/v1/visit-asset-situations",
            headers={"X-Integration-Key": key.json()["secret"]},
        )
        assert exported.status_code == 200
        assert {
            (item["asset_id"], item["situation"], item["comment"])
            for item in exported.json()["items"]
        } == {(aerator["id"], "FUNCIONANDO", None), (pump["id"], "OUTRO", "Emprestada")}

    async with session_factory() as session:
        total = await session.scalar(
            select(func.count())
            .select_from(VisitAssetSituation)
            .where(VisitAssetSituation.tenant_id == tenant_id)
        )
        assert total == 2
