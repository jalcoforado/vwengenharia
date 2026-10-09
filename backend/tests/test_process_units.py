from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import ProcessUnitType


@pytest.mark.asyncio
async def test_process_units_sit_between_station_and_asset() -> None:
    suffix = uuid4().hex[:10]
    admin_email = f"unidade-admin-{suffix}@example.com"
    password = "senha-segura-123"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Unidade A {suffix}", slug=f"unidade-a-{suffix}")
        tenant_b = Tenant(name=f"Unidade B {suffix}", slug=f"unidade-b-{suffix}")
        admin = User(email=admin_email, name="Admin", password_hash=hash_password(password))
        session.add_all([tenant_a, tenant_b, admin])
        await session.flush()
        session.add(Membership(tenant_id=tenant_a.id, user_id=admin.id, role=Role.ADMIN.value))
        foreign_type = ProcessUnitType(tenant_id=tenant_b.id, name=f"Tipo externo {suffix}")
        session.add(foreign_type)
        await session.commit()
        foreign_type_id = foreign_type.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login", json={"email": admin_email, "password": password}
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        async def create(path: str, body: dict) -> dict:
            response = await http.post(path, headers=headers, json=body)
            assert response.status_code == 201, response.text
            return response.json()

        uasb_type = await create(
            "/api/v1/process-unit-types",
            {"name": f"Reator UASB {suffix}", "code": f"U11-{suffix}", "stage": "Secundário anaeróbio"},
        )
        assert uasb_type["stage"] == "Secundário anaeróbio"
        contact_type = await create(
            "/api/v1/process-unit-types", {"name": f"Tanque de contato {suffix}"}
        )

        repeated_type = await http.post(
            "/api/v1/process-unit-types",
            headers=headers,
            json={"name": f"Reator UASB {suffix}"},
        )
        assert repeated_type.status_code == 409
        repeated_code = await http.post(
            "/api/v1/process-unit-types",
            headers=headers,
            json={"name": f"Outro {suffix}", "code": f"U11-{suffix}"},
        )
        assert repeated_code.status_code == 409

        responsible = await create("/api/v1/clients", {"name": f"Sindica {suffix}"})
        development = await create(
            "/api/v1/developments",
            {"client_id": responsible["id"], "name": f"Condominio {suffix}"},
        )
        station_a = await create(
            "/api/v1/stations",
            {"development_id": development["id"], "name": f"ETE A {suffix}", "code": f"A-{suffix}"},
        )
        station_b = await create(
            "/api/v1/stations",
            {"development_id": development["id"], "name": f"ETE B {suffix}", "code": f"B-{suffix}"},
        )

        uasb = await create(
            "/api/v1/process-units",
            {"station_id": station_a["id"], "unit_type_id": uasb_type["id"], "name": "UASB 1"},
        )
        # O mesmo nome pode existir em outra estacao, mas nao se repete na mesma.
        other_station_unit = await create(
            "/api/v1/process-units",
            {"station_id": station_b["id"], "unit_type_id": uasb_type["id"], "name": "UASB 1"},
        )
        repeated_unit = await http.post(
            "/api/v1/process-units",
            headers=headers,
            json={"station_id": station_a["id"], "unit_type_id": uasb_type["id"], "name": "UASB 1"},
        )
        assert repeated_unit.status_code == 409

        foreign_type_unit = await http.post(
            "/api/v1/process-units",
            headers=headers,
            json={
                "station_id": station_a["id"],
                "unit_type_id": str(foreign_type_id),
                "name": "Nao deve criar",
            },
        )
        assert foreign_type_unit.status_code == 404

        by_station = await http.get(
            "/api/v1/process-units", headers=headers, params={"station_id": station_a["id"]}
        )
        assert [item["id"] for item in by_station.json()] == [uasb["id"]]

        retyped = await http.patch(
            f"/api/v1/process-units/{uasb['id']}",
            headers=headers,
            json={"unit_type_id": contact_type["id"], "name": "Tanque 1"},
        )
        assert retyped.status_code == 200
        assert retyped.json()["unit_type_id"] == contact_type["id"]

        asset_type = await create("/api/v1/asset-types", {"name": f"Bomba {suffix}"})
        asset = await create(
            "/api/v1/assets",
            {
                "station_id": station_a["id"],
                "asset_type_id": asset_type["id"],
                "process_unit_id": uasb["id"],
                "name": "Bomba de recirculacao I",
            },
        )
        assert asset["process_unit_id"] == uasb["id"]

        # Equipamento sem unidade continua valido (area geral da estacao).
        loose = await create(
            "/api/v1/assets",
            {"station_id": station_a["id"], "asset_type_id": asset_type["id"], "name": "Portao"},
        )
        assert loose["process_unit_id"] is None

        wrong_station = await http.post(
            "/api/v1/assets",
            headers=headers,
            json={
                "station_id": station_a["id"],
                "asset_type_id": asset_type["id"],
                "process_unit_id": other_station_unit["id"],
                "name": "Nao deve criar",
            },
        )
        assert wrong_station.status_code == 422
        assert wrong_station.json()["detail"] == "process_unit_not_in_station"

        moved_to_wrong_unit = await http.patch(
            f"/api/v1/assets/{asset['id']}",
            headers=headers,
            json={"process_unit_id": other_station_unit["id"]},
        )
        assert moved_to_wrong_unit.status_code == 422

        # Mudar de estacao sem trocar a unidade tambem e barrado.
        moved_station_only = await http.patch(
            f"/api/v1/assets/{asset['id']}",
            headers=headers,
            json={"station_id": station_b["id"]},
        )
        assert moved_station_only.status_code == 422

        moved = await http.patch(
            f"/api/v1/assets/{asset['id']}",
            headers=headers,
            json={"station_id": station_b["id"], "process_unit_id": other_station_unit["id"]},
        )
        assert moved.status_code == 200

        detached = await http.patch(
            f"/api/v1/assets/{asset['id']}", headers=headers, json={"process_unit_id": None}
        )
        assert detached.status_code == 200
        assert detached.json()["process_unit_id"] is None

        key = await http.post(
            "/api/v1/integration-keys", headers=headers, json={"name": "iAnalisys"}
        )
        integration_headers = {"X-Integration-Key": key.json()["secret"]}
        units = await http.get(
            "/api/v1/integration/v1/process-units", headers=integration_headers
        )
        assert units.status_code == 200
        assert {item["id"] for item in units.json()["items"]} == {
            uasb["id"],
            other_station_unit["id"],
        }
        unit_types = await http.get(
            "/api/v1/integration/v1/process-unit-types", headers=integration_headers
        )
        assert {item["name"] for item in unit_types.json()["items"]} == {
            f"Reator UASB {suffix}",
            f"Tanque de contato {suffix}",
        }
        assets = await http.get("/api/v1/integration/v1/assets", headers=integration_headers)
        assert all("process_unit_id" in item for item in assets.json()["items"])
