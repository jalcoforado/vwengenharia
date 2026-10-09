from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import ContractingParty


@pytest.mark.asyncio
async def test_contracting_party_owns_many_developments() -> None:
    suffix = uuid4().hex[:10]
    admin_email = f"contratante-admin-{suffix}@example.com"
    password = "senha-segura-123"
    document = f"CNPJ-{suffix}"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Contratante A {suffix}", slug=f"contratante-a-{suffix}")
        tenant_b = Tenant(name=f"Contratante B {suffix}", slug=f"contratante-b-{suffix}")
        admin = User(email=admin_email, name="Admin", password_hash=hash_password(password))
        session.add_all([tenant_a, tenant_b, admin])
        await session.flush()
        session.add(Membership(tenant_id=tenant_a.id, user_id=admin.id, role=Role.ADMIN.value))
        foreign = ContractingParty(
            tenant_id=tenant_b.id, person_type="PJ", name="Outro Tenant", document=document
        )
        session.add(foreign)
        await session.commit()
        tenant_a_id = tenant_a.id
        foreign_id = foreign.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login", json={"email": admin_email, "password": password}
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        party = await http.post(
            "/api/v1/contracting-parties",
            headers=headers,
            json={
                "person_type": "PJ",
                "name": f"Construtora {suffix} Ltda",
                "trade_name": f"Construtora {suffix}",
                "document": document,
                "contact_email": f"contato-{suffix}@example.com",
                "contact_phone": "(85) 3333-0000",
            },
        )
        assert party.status_code == 201
        party_id = party.json()["id"]
        assert party.json()["person_type"] == "PJ"

        duplicate = await http.post(
            "/api/v1/contracting-parties",
            headers=headers,
            json={"name": "Repetido", "document": document},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "contracting_party_document_already_exists"

        person = await http.post(
            "/api/v1/contracting-parties",
            headers=headers,
            json={"person_type": "PF", "name": f"Pessoa {suffix}"},
        )
        assert person.status_code == 201

        taken = await http.patch(
            f"/api/v1/contracting-parties/{person.json()['id']}",
            headers=headers,
            json={"document": document},
        )
        assert taken.status_code == 409

        renamed = await http.patch(
            f"/api/v1/contracting-parties/{party_id}",
            headers=headers,
            json={"trade_name": "Novo Nome", "document": document},
        )
        assert renamed.status_code == 200
        assert renamed.json()["trade_name"] == "Novo Nome"

        responsible = await http.post(
            "/api/v1/clients", headers=headers, json={"name": f"Sindico {suffix}"}
        )
        assert responsible.status_code == 201

        # Uma mesma empresa contratante com dois locais atendidos.
        development_ids = []
        for label in ("Norte", "Sul"):
            development = await http.post(
                "/api/v1/developments",
                headers=headers,
                json={
                    "client_id": responsible.json()["id"],
                    "contracting_party_id": party_id,
                    "name": f"Loteamento {label} {suffix}",
                },
            )
            assert development.status_code == 201
            assert development.json()["contracting_party_id"] == party_id
            development_ids.append(development.json()["id"])

        foreign_party = await http.post(
            "/api/v1/developments",
            headers=headers,
            json={
                "client_id": responsible.json()["id"],
                "contracting_party_id": str(foreign_id),
                "name": "Nao deve criar",
            },
        )
        assert foreign_party.status_code == 404

        foreign_on_update = await http.patch(
            f"/api/v1/developments/{development_ids[0]}",
            headers=headers,
            json={"contracting_party_id": str(foreign_id)},
        )
        assert foreign_on_update.status_code == 404

        listed = await http.get("/api/v1/contracting-parties", headers=headers)
        assert listed.status_code == 200
        assert {item["id"] for item in listed.json()} == {party_id, person.json()["id"]}

        key = await http.post(
            "/api/v1/integration-keys", headers=headers, json={"name": "iAnalisys"}
        )
        integration_headers = {"X-Integration-Key": key.json()["secret"]}

        exported = await http.get(
            "/api/v1/integration/v1/contracting-parties", headers=integration_headers
        )
        assert exported.status_code == 200
        assert exported.json()["tenant_id"] == str(tenant_a_id)
        exported_party = next(item for item in exported.json()["items"] if item["id"] == party_id)
        assert exported_party["document"] == document
        assert exported_party["trade_name"] == "Novo Nome"

        developments = await http.get(
            "/api/v1/integration/v1/developments", headers=integration_headers
        )
        assert {
            item["contracting_party_id"]
            for item in developments.json()["items"]
            if item["id"] in development_ids
        } == {party_id}
