from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Station
from app.modules.core_registers.service import development_sigla, station_code_prefix


def test_station_code_prefix_uses_type_and_development_initials() -> None:
    assert development_sigla("Residencial Lago Azul") == "RLA"
    assert development_sigla("Condomínio Jardim das Águas") == "CJA"
    assert development_sigla("Ipanema") == "IPA"
    assert development_sigla("  ") == "EMP"
    assert station_code_prefix("ETE", "Residencial Lago Azul") == "ETE-RLA-"
    assert station_code_prefix("ELEVATORIA", "Parque Verde") == "ELV-PV-"
    assert station_code_prefix("OUTRA", "Parque Verde") == "EST-PV-"
    assert station_code_prefix("Booster", "Parque Verde") == "BOO-PV-"


@pytest.mark.asyncio
async def test_station_code_is_generated_fixed_and_type_frequency_required() -> None:
    suffix = uuid4().hex[:10]
    admin_email = f"estacao-admin-{suffix}@example.com"
    password = "senha-segura-123"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Estacoes {suffix}", slug=f"estacoes-{suffix}")
        admin = User(email=admin_email, name="Admin", password_hash=hash_password(password))
        session.add_all([tenant, admin])
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=admin.id, role=Role.ADMIN.value))
        await session.commit()
        tenant_id = tenant.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login", json={"email": admin_email, "password": password}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        responsible = await http.post(
            "/api/v1/clients", headers=headers, json={"name": f"Sindico {suffix}"}
        )
        development = await http.post(
            "/api/v1/developments",
            headers=headers,
            json={"client_id": responsible.json()["id"], "name": "Residencial Lago Azul"},
        )
        development_id = development.json()["id"]

        async def create_station(body: dict):
            return await http.post(
                "/api/v1/stations",
                headers=headers,
                json={"development_id": development_id, "name": f"Estacao {uuid4().hex[:6]}", **body},
            )

        # Tipo e frequencia sao obrigatorios.
        assert (await create_station({"visit_frequency_days": 7})).status_code == 422
        assert (await create_station({"station_type": "ETE"})).status_code == 422

        first = await create_station({"station_type": "ETE", "visit_frequency_days": 7})
        second = await create_station({"station_type": "ETE", "visit_frequency_days": 7})
        lift = await create_station({"station_type": "ELEVATORIA", "visit_frequency_days": 1})
        assert first.status_code == 201
        assert first.json()["code"] == "ETE-RLA-01"
        assert second.json()["code"] == "ETE-RLA-02"
        assert lift.json()["code"] == "ELV-RLA-01"

        # Codigo informado (carga de dados) e normalizado e nao pode repetir.
        loaded = await create_station(
            {"station_type": "ETA", "visit_frequency_days": 30, "code": " eta-legado-7 "}
        )
        assert loaded.json()["code"] == "ETA-LEGADO-7"
        repeated = await create_station(
            {"station_type": "ETA", "visit_frequency_days": 30, "code": "ETE-RLA-01"}
        )
        assert repeated.status_code == 409
        assert repeated.json()["detail"] == "station_code_already_exists"

        # O codigo nao e editavel: o campo enviado e ignorado; nome e frequencia nao mexem nele.
        station_url = f"/api/v1/stations/{first.json()['id']}"
        renamed = await http.patch(
            station_url,
            headers=headers,
            json={"name": f"ETE Principal {suffix}", "visit_frequency_days": 15, "code": "OUTRO-99"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["code"] == "ETE-RLA-01"

        # Trocar o tipo refaz o codigo no padrao do novo tipo.
        retyped = await http.patch(station_url, headers=headers, json={"station_type": "ETA"})
        assert retyped.status_code == 200
        assert retyped.json()["station_type"] == "ETA"
        assert retyped.json()["code"] == "ETA-RLA-01"
        back = await http.patch(station_url, headers=headers, json={"station_type": "ETE"})
        assert back.json()["code"] == "ETE-RLA-03"

        # Trocar o empreendimento tambem refaz o codigo.
        other_development = await http.post(
            "/api/v1/developments",
            headers=headers,
            json={"client_id": responsible.json()["id"], "name": "Parque Verde"},
        )
        moved = await http.patch(
            station_url,
            headers=headers,
            json={"development_id": other_development.json()["id"]},
        )
        assert moved.json()["code"] == "ETE-PV-01"

        # Codigo antigo fora do padrao so muda quando tipo ou empreendimento mudam.
        legacy_named = await http.patch(
            f"/api/v1/stations/{loaded.json()['id']}", headers=headers, json={"name": f"Legado {suffix}"}
        )
        assert legacy_named.json()["code"] == "ETA-LEGADO-7"

        cleared = await http.patch(
            station_url, headers=headers, json={"visit_frequency_days": None}
        )
        assert cleared.status_code == 422

    # Estacao antiga sem codigo ganha o codigo na primeira edicao.
    async with session_factory() as session:
        legacy = Station(
            tenant_id=tenant_id,
            development_id=development_id,
            name=f"Antiga {suffix}",
            station_type="ETE",
            visit_frequency_days=7,
        )
        session.add(legacy)
        await session.commit()
        legacy_id = legacy.id

    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login", json={"email": admin_email, "password": password}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        coded = await http.patch(
            f"/api/v1/stations/{legacy_id}", headers=headers, json={"name": f"Antiga ETE {suffix}"}
        )
        assert coded.status_code == 200
        # ETE-RLA-03 saiu para outro empreendimento, mas o numero nao volta a ser usado.
        assert coded.json()["code"] == "ETE-RLA-04"
