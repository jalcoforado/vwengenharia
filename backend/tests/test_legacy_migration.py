from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.main import app
from app.models.field import Visit
from app.models.identity import Membership, Role, Tenant, User
from app.models.legacy import LegacyVisitStage
from app.models.operations import Client, Development, Station


def legacy_workbook_bytes(
    *,
    technician: str,
    station: str,
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Página1"
    sheet.append(
        [
            "Added Time",
            "IP Address",
            "Técnico",
            "Estações",
            "Nome",
            "Registro",
            "Data e Hora",
            "Status",
            "Observações:",
        ]
    )
    sheet.append(
        [
            datetime(2026, 8, 17, 10, 6),
            "127.0.0.1",
            technician,
            station,
            technician,
            datetime(2026, 8, 17, 10, 5),
            datetime(2026, 8, 17, 10, 4),
            "Aguardando Revisão",
            "Registro histórico de teste.",
        ]
    )
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


@pytest.mark.asyncio
async def test_legacy_xlsx_staging_mapping_and_materialization() -> None:
    suffix = uuid4().hex[:10]
    password = "senha-segura-123"
    email = f"legacy-admin-{suffix}@example.com"
    technician_name = f"Tecnico Legacy {suffix}"
    station_name = f"ETE Legacy {suffix}"

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = Tenant(name=f"Legacy {suffix}", slug=f"legacy-{suffix}")
        admin = User(
            email=email,
            name="Admin Legacy",
            password_hash=hash_password(password),
        )
        technician = User(
            email=f"tech-{suffix}@example.com",
            name=technician_name,
            password_hash=hash_password(password),
        )
        session.add_all([tenant, admin, technician])
        await session.flush()
        session.add_all(
            [
                Membership(
                    tenant_id=tenant.id,
                    user_id=admin.id,
                    role=Role.ADMIN.value,
                ),
                Membership(
                    tenant_id=tenant.id,
                    user_id=technician.id,
                    role=Role.TECNICO.value,
                ),
            ]
        )
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
            name=station_name,
            is_active=True,
        )
        session.add(station)
        await session.commit()
        tenant_id = tenant.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        login = await http.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        content = legacy_workbook_bytes(
            technician=technician_name,
            station=station_name,
        )
        staged = await http.post(
            "/api/v1/legacy-migration/stage",
            headers=headers,
            files={
                "file": (
                    "Visitas MW teste.xlsx",
                    content,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            data={"sheet": "Página1"},
        )
        assert staged.status_code == 200
        assert staged.json()["staged"] == 1
        assert staged.json()["errors"] == 0

        staged_again = await http.post(
            "/api/v1/legacy-migration/stage",
            headers=headers,
            files={
                "file": (
                    "Visitas MW teste.xlsx",
                    content,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            data={"sheet": "Página1"},
        )
        assert staged_again.status_code == 200
        assert staged_again.json()["staged"] == 0
        assert staged_again.json()["skipped_existing"] == 1

        summary = await http.get(
            "/api/v1/legacy-migration/summary",
            headers=headers,
        )
        assert summary.status_code == 200
        assert station_name in summary.json()["unmapped_station_labels"]
        assert technician_name in summary.json()["unmapped_technician_labels"]

        auto_map = await http.post(
            "/api/v1/legacy-migration/auto-map",
            headers=headers,
        )
        assert auto_map.status_code == 200
        assert auto_map.json() == {
            "stations_mapped": 1,
            "technicians_mapped": 1,
        }

        materialized = await http.post(
            "/api/v1/legacy-migration/materialize",
            headers=headers,
            json={
                "limit": 100,
                "preserve_source_review_status": False,
            },
        )
        assert materialized.status_code == 200
        assert materialized.json()["imported"] == 1
        assert materialized.json()["errors"] == 0

    async with session_factory() as session:
        visits = list(
            (
                await session.execute(
                    select(Visit).where(Visit.tenant_id == tenant_id)
                )
            ).scalars()
        )
        assert len(visits) == 1
        assert visits[0].status == "REVISADA"
        assert visits[0].scheduled_for == datetime(
            2026,
            8,
            17,
            13,
            4,
            tzinfo=UTC,
        )

        stage = (
            await session.execute(
                select(LegacyVisitStage).where(
                    LegacyVisitStage.tenant_id == tenant_id
                )
            )
        ).scalar_one()
        assert stage.status == "IMPORTED"
        assert stage.source_status == "Aguardando Revisão"
        assert stage.imported_visit_id == visits[0].id
