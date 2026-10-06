from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.field import Attachment, Visit, VisitStatus
from app.models.identity import Membership, Role, Tenant, User
from app.models.operations import Client, Development, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.field import service as field_service


class FakeStorage:
    def object_metadata(self, *, object_key: str) -> dict:
        return {
            "ContentLength": 1234,
            "ContentType": "image/jpeg",
        }


@pytest.mark.asyncio
async def test_complete_attachment_marks_verified_evidence(monkeypatch) -> None:
    suffix = uuid4().hex[:10]
    session_factory = get_session_factory()

    async with session_factory() as session:
        tenant = Tenant(name=f"Storage {suffix}", slug=f"storage-{suffix}")
        user = User(
            email=f"storage-{suffix}@example.com",
            name="Tecnico Storage",
            password_hash=hash_password("senha-segura-123"),
        )
        session.add_all([tenant, user])
        await session.flush()

        membership = Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=Role.TECNICO.value,
        )
        client = Client(tenant_id=tenant.id, name=f"Cliente {suffix}")
        session.add_all([membership, client])
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
            code=f"STG-{suffix}",
        )
        session.add(station)
        await session.flush()

        visit = Visit(
            tenant_id=tenant.id,
            station_id=station.id,
            technician_membership_id=membership.id,
            scheduled_for=datetime.now(UTC),
            status=VisitStatus.EM_EXECUCAO.value,
        )
        session.add(visit)
        await session.flush()

        attachment = Attachment(
            tenant_id=tenant.id,
            visit_id=visit.id,
            object_key=f"{tenant.id}/visits/{visit.id}/evidence.jpg",
            content_type="image/jpeg",
            size_bytes=1234,
            storage_status="PENDING",
        )
        session.add(attachment)
        await session.commit()

        context = AuthContext(
            user=user,
            membership=membership,
            tenant=tenant,
        )
        attachment_id = attachment.id

    fake = FakeStorage()
    monkeypatch.setattr(field_service, "get_storage", lambda: fake)

    async with session_factory() as session:
        completed = await field_service.complete_attachment_upload(
            session,
            context,
            attachment_id,
        )
        assert completed.storage_status == "UPLOADED"
        assert completed.uploaded_at is not None

    async with session_factory() as session:
        stored = await session.scalar(
            select(Attachment).where(Attachment.id == attachment_id)
        )
        assert stored is not None
        assert stored.storage_status == "UPLOADED"
