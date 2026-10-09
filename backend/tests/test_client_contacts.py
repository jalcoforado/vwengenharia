from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.audit import AuditEvent
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Client, Development


@pytest.mark.asyncio
async def test_client_contacts_link_clients_to_developments_by_scope() -> None:
    suffix = uuid4().hex[:10]
    admin_email = f"admin-contacts-{suffix}@example.com"
    password = "senha-segura-123"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Contatos A {suffix}", slug=f"contatos-a-{suffix}")
        tenant_b = Tenant(name=f"Contatos B {suffix}", slug=f"contatos-b-{suffix}")
        admin = User(
            email=admin_email,
            name="Admin Contatos",
            password_hash=hash_password(password),
        )
        session.add_all([tenant_a, tenant_b, admin])
        await session.flush()
        session.add(
            Membership(tenant_id=tenant_a.id, user_id=admin.id, role=Role.ADMIN.value)
        )
        foreign_client = Client(tenant_id=tenant_b.id, name=f"Cliente Externo {suffix}")
        session.add(foreign_client)
        await session.flush()
        foreign_development = Development(
            tenant_id=tenant_b.id,
            client_id=foreign_client.id,
            name=f"Empreendimento Externo {suffix}",
        )
        session.add(foreign_development)
        await session.commit()
        tenant_a_id = tenant_a.id
        foreign_client_id = foreign_client.id
        foreign_development_id = foreign_development.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": password},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        sindico = await http.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "name": f"Maria Sindica {suffix}",
                "contact_role": "Sindica",
                "contact_phone": "8533330000",
                "contact_whatsapp": "85999990000",
                "contact_email": f"maria-{suffix}@example.com",
            },
        )
        assert sindico.status_code == 201
        assert sindico.json()["contact_role"] == "Sindica"
        assert sindico.json()["contact_whatsapp"] == "85999990000"
        sindico_id = sindico.json()["id"]

        financeiro = await http.post(
            "/api/v1/clients",
            headers=headers,
            json={"name": f"Joao Financeiro {suffix}", "contact_role": "Financeiro"},
        )
        assert financeiro.status_code == 201
        financeiro_id = financeiro.json()["id"]

        development_ids = []
        for label in ("Lago", "Serra"):
            development = await http.post(
                "/api/v1/developments",
                headers=headers,
                json={"client_id": sindico_id, "name": f"Residencial {label} {suffix}"},
            )
            assert development.status_code == 201
            development_ids.append(development.json()["id"])
        lago_id, serra_id = development_ids

        # Uma pessoa responde por mais de um empreendimento.
        created_ids = []
        for development_id in (lago_id, serra_id):
            link = await http.post(
                "/api/v1/client-contacts",
                headers=headers,
                json={
                    "client_id": sindico_id,
                    "development_id": development_id,
                    "scope": "TECNICO",
                },
            )
            assert link.status_code == 201
            assert link.json()["is_active"] is True
            created_ids.append(link.json()["id"])

        # Um empreendimento tem mais de um responsavel, cada um em sua area.
        second = await http.post(
            "/api/v1/client-contacts",
            headers=headers,
            json={
                "client_id": financeiro_id,
                "development_id": lago_id,
                "scope": "FINANCEIRO",
            },
        )
        assert second.status_code == 201

        duplicate = await http.post(
            "/api/v1/client-contacts",
            headers=headers,
            json={"client_id": sindico_id, "development_id": lago_id, "scope": "TECNICO"},
        )
        assert duplicate.status_code == 409

        invalid_scope = await http.post(
            "/api/v1/client-contacts",
            headers=headers,
            json={"client_id": sindico_id, "development_id": lago_id, "scope": "OUTRO"},
        )
        assert invalid_scope.status_code == 422

        foreign_client_link = await http.post(
            "/api/v1/client-contacts",
            headers=headers,
            json={
                "client_id": str(foreign_client_id),
                "development_id": lago_id,
                "scope": "TECNICO",
            },
        )
        assert foreign_client_link.status_code == 404

        foreign_development_link = await http.post(
            "/api/v1/client-contacts",
            headers=headers,
            json={
                "client_id": sindico_id,
                "development_id": str(foreign_development_id),
                "scope": "TECNICO",
            },
        )
        assert foreign_development_link.status_code == 404

        by_development = await http.get(
            "/api/v1/client-contacts",
            headers=headers,
            params={"development_id": lago_id},
        )
        assert by_development.status_code == 200
        assert {(item["client_id"], item["scope"]) for item in by_development.json()} == {
            (sindico_id, "TECNICO"),
            (financeiro_id, "FINANCEIRO"),
        }

        by_client = await http.get(
            "/api/v1/client-contacts",
            headers=headers,
            params={"client_id": sindico_id},
        )
        assert {item["development_id"] for item in by_client.json()} == {lago_id, serra_id}

        same_scope = await http.patch(
            f"/api/v1/client-contacts/{created_ids[0]}",
            headers=headers,
            json={"scope": "TECNICO"},
        )
        assert same_scope.status_code == 200

        deactivated = await http.patch(
            f"/api/v1/client-contacts/{created_ids[1]}",
            headers=headers,
            json={"is_active": False},
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False

        key = await http.post(
            "/api/v1/integration-keys",
            headers=headers,
            json={"name": "iAnalisys"},
        )
        assert key.status_code == 201
        integration_headers = {"X-Integration-Key": key.json()["secret"]}

        exported = await http.get(
            "/api/v1/integration/v1/client-contacts",
            headers=integration_headers,
        )
        assert exported.status_code == 200
        body = exported.json()
        assert body["tenant_id"] == str(tenant_a_id)
        assert len(body["items"]) == 3
        lago_tecnico = next(
            item
            for item in body["items"]
            if item["development_id"] == lago_id and item["scope"] == "TECNICO"
        )
        assert lago_tecnico["client_id"] == sindico_id
        assert lago_tecnico["name"] == f"Maria Sindica {suffix}"
        assert lago_tecnico["contact_role"] == "Sindica"
        assert lago_tecnico["contact_phone"] == "8533330000"
        assert lago_tecnico["contact_whatsapp"] == "85999990000"
        assert lago_tecnico["contact_email"] == f"maria-{suffix}@example.com"
        snapshot = body["generated_at"]

        exported_clients = await http.get(
            "/api/v1/integration/v1/clients",
            headers=integration_headers,
        )
        exported_sindico = next(
            item for item in exported_clients.json()["items"] if item["id"] == sindico_id
        )
        assert exported_sindico["contact_whatsapp"] == "85999990000"

        # Alterar o cliente reexporta as linhas dele na carga incremental.
        updated = await http.patch(
            f"/api/v1/clients/{sindico_id}",
            headers=headers,
            json={"contact_whatsapp": "85988887777"},
        )
        assert updated.status_code == 200

        incremental = await http.get(
            "/api/v1/integration/v1/client-contacts",
            headers=integration_headers,
            params={"updated_since": snapshot},
        )
        assert incremental.status_code == 200
        items = incremental.json()["items"]
        assert {item["development_id"] for item in items} == {lago_id, serra_id}
        assert {item["contact_whatsapp"] for item in items} == {"85988887777"}

    async with session_factory() as session:
        audited = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.tenant_id == tenant_a_id,
                AuditEvent.action.in_(["CLIENT_CONTACT_CREATE", "CLIENT_CONTACT_UPDATE"]),
            )
        )
        assert audited == 5


@pytest.mark.asyncio
async def test_client_document_is_unique_per_tenant() -> None:
    suffix = uuid4().hex[:10]
    admin_email = f"admin-document-{suffix}@example.com"
    password = "senha-segura-123"
    document = f"DOC-{suffix}"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_a = Tenant(name=f"Documento A {suffix}", slug=f"documento-a-{suffix}")
        tenant_b = Tenant(name=f"Documento B {suffix}", slug=f"documento-b-{suffix}")
        admin = User(
            email=admin_email,
            name="Admin Documento",
            password_hash=hash_password(password),
        )
        session.add_all([tenant_a, tenant_b, admin])
        await session.flush()
        session.add(
            Membership(tenant_id=tenant_a.id, user_id=admin.id, role=Role.ADMIN.value)
        )
        # O mesmo documento em outro tenant nao gera conflito.
        session.add(Client(tenant_id=tenant_b.id, name="Outro Tenant", document=document))
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": password},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        first = await http.post(
            "/api/v1/clients",
            headers=headers,
            json={"name": f"Primeiro {suffix}", "document": document},
        )
        assert first.status_code == 201

        duplicate = await http.post(
            "/api/v1/clients",
            headers=headers,
            json={"name": f"Repetido {suffix}", "document": document},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "client_document_already_exists"

        second = await http.post(
            "/api/v1/clients",
            headers=headers,
            json={"name": f"Segundo {suffix}"},
        )
        assert second.status_code == 201

        taken = await http.patch(
            f"/api/v1/clients/{second.json()['id']}",
            headers=headers,
            json={"document": document},
        )
        assert taken.status_code == 409

        same_client = await http.patch(
            f"/api/v1/clients/{first.json()['id']}",
            headers=headers,
            json={"document": document, "contact_role": "Sindico"},
        )
        assert same_client.status_code == 200
