from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.ai import AiRun
from app.models.identity import Membership, Role, Tenant, User
from app.models.maintenance import WorkOrder, WorkOrderPriority, WorkOrderStatus
from app.models.operations import Client, Development, Station
from app.modules.ai.tools import execute_tool
from app.modules.auth.dependencies import AuthContext


@pytest.mark.asyncio
async def test_ai_tools_are_tenant_scoped_and_disabled_provider_is_audited() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    session_factory = get_session_factory()

    async with session_factory() as session:
        tenant_a = Tenant(name=f"AI A {suffix}", slug=f"ai-a-{suffix}")
        tenant_b = Tenant(name=f"AI B {suffix}", slug=f"ai-b-{suffix}")
        user = User(
            email=f"ai-{suffix}@example.com",
            name="Gestor IA",
            password_hash=hash_password(password),
        )
        session.add_all([tenant_a, tenant_b, user])
        await session.flush()
        membership = Membership(
            tenant_id=tenant_a.id,
            user_id=user.id,
            role=Role.GESTOR.value,
        )
        client_a = Client(tenant_id=tenant_a.id, name="Cliente A")
        client_b = Client(tenant_id=tenant_b.id, name="Cliente B")
        session.add_all([membership, client_a, client_b])
        await session.flush()
        dev_a = Development(tenant_id=tenant_a.id, client_id=client_a.id, name="Dev A")
        dev_b = Development(tenant_id=tenant_b.id, client_id=client_b.id, name="Dev B")
        session.add_all([dev_a, dev_b])
        await session.flush()
        station_a = Station(
            tenant_id=tenant_a.id,
            development_id=dev_a.id,
            name="ETE Visivel",
            code=f"A-{suffix}",
        )
        station_b = Station(
            tenant_id=tenant_b.id,
            development_id=dev_b.id,
            name="ETE Outro Tenant",
            code=f"B-{suffix}",
        )
        session.add_all([station_a, station_b])
        await session.flush()
        now = datetime.now(UTC)
        session.add_all(
            [
                WorkOrder(
                    tenant_id=tenant_a.id,
                    station_id=station_a.id,
                    priority=WorkOrderPriority.CRITICA.value,
                    status=WorkOrderStatus.ABERTA.value,
                    description="Falha critica visivel",
                    sla_due_at=now + timedelta(hours=1),
                ),
                WorkOrder(
                    tenant_id=tenant_b.id,
                    station_id=station_b.id,
                    priority=WorkOrderPriority.CRITICA.value,
                    status=WorkOrderStatus.ABERTA.value,
                    description="Segredo de outro tenant",
                    sla_due_at=now + timedelta(hours=1),
                ),
            ]
        )
        await session.commit()
        context = AuthContext(user=user, membership=membership, tenant=tenant_a)
        tenant_a_id = tenant_a.id

    async with session_factory() as session:
        result = await execute_tool(
            session,
            context,
            "list_open_work_orders",
            {"priority": "CRITICA", "limit": 20},
        )
        assert len(result) == 1
        assert result[0]["station"] == "ETE Visivel"
        assert result[0]["description"] == "Falha critica visivel"

        search = await execute_tool(
            session,
            context,
            "search_stations",
            {"query": "ETE", "limit": 10},
        )
        assert [item["name"] for item in search] == ["ETE Visivel"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        answer = await http.post(
            "/api/v1/ai/ask",
            headers=headers,
            json={"question": "Quais sao os principais riscos agora?"},
        )
        assert answer.status_code == 503
        assert answer.json()["detail"] == "ai_provider_disabled"

    async with session_factory() as session:
        runs = list(
            (
                await session.execute(
                    select(AiRun).where(AiRun.tenant_id == tenant_a_id)
                )
            ).scalars()
        )
        assert len(runs) == 1
        assert runs[0].status == "FAILED"
        assert runs[0].error_code == "ai_provider_disabled"
