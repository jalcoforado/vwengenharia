import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import Measurement, Visit, VisitPlan
from app.models.integration import IntegrationCredential
from app.models.maintenance import (
    Occurrence,
    VisitReview,
    WorkOrder,
    WorkOrderStatusHistory,
)
from app.models.operations import Asset, Client, Development, Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit
from app.modules.integration.dependencies import IntegrationContext
from app.modules.integration.schemas import IntegrationKeyCreate, IntegrationResource


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


async def create_integration_key(
    session: AsyncSession,
    context: AuthContext,
    payload: IntegrationKeyCreate,
) -> tuple[IntegrationCredential, str]:
    name = payload.name.strip()
    existing = (
        await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.tenant_id == context.tenant.id,
                IntegrationCredential.name == name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="integration_key_name_exists",
        )

    secret = "vwk_" + secrets.token_urlsafe(32)
    credential = IntegrationCredential(
        tenant_id=context.tenant.id,
        name=name,
        key_prefix=secret[:12],
        key_hash=_hash_secret(secret),
        created_by_user_id=context.user.id,
    )
    session.add(credential)
    await session.flush()
    add_audit(
        session,
        context,
        action="INTEGRATION_KEY_CREATE",
        entity_type="integration_credential",
        entity_id=credential.id,
        fields=["name", "key_prefix"],
    )
    await session.commit()
    await session.refresh(credential)
    return credential, secret


async def list_integration_keys(
    session: AsyncSession,
    context: AuthContext,
) -> list[IntegrationCredential]:
    stmt = (
        select(IntegrationCredential)
        .where(IntegrationCredential.tenant_id == context.tenant.id)
        .order_by(IntegrationCredential.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def revoke_integration_key(
    session: AsyncSession,
    context: AuthContext,
    credential_id: UUID,
) -> IntegrationCredential:
    credential = (
        await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.id == credential_id,
                IntegrationCredential.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="integration_key_not_found",
        )
    if credential.revoked_at is None:
        credential.revoked_at = datetime.now(UTC)
        add_audit(
            session,
            context,
            action="INTEGRATION_KEY_REVOKE",
            entity_type="integration_credential",
            entity_id=credential.id,
            fields=["revoked_at"],
        )
        await session.commit()
        await session.refresh(credential)
    return credential


def _base_payload(row) -> dict:
    return {
        "id": row.id,
        "created_at": getattr(row, "created_at", None),
        "updated_at": getattr(row, "updated_at", None),
    }


def _serialize(resource: IntegrationResource, row) -> dict:
    payload = _base_payload(row)

    if resource == IntegrationResource.CLIENTS:
        payload.update(
            {
                "name": row.name,
                "document": row.document,
                "contact_name": row.contact_name,
                "contact_email": row.contact_email,
                "contact_phone": row.contact_phone,
                "is_active": row.is_active,
            }
        )
    elif resource == IntegrationResource.DEVELOPMENTS:
        payload.update(
            {
                "client_id": row.client_id,
                "name": row.name,
                "address_line": row.address_line,
                "city": row.city,
                "state": row.state,
                "postal_code": row.postal_code,
                "is_active": row.is_active,
            }
        )
    elif resource == IntegrationResource.STATIONS:
        payload.update(
            {
                "development_id": row.development_id,
                "name": row.name,
                "code": row.code,
                "station_type": row.station_type,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "visit_frequency_days": row.visit_frequency_days,
                "is_active": row.is_active,
            }
        )
    elif resource == IntegrationResource.ASSETS:
        payload.update(
            {
                "station_id": row.station_id,
                "asset_type_id": row.asset_type_id,
                "name": row.name,
                "manufacturer": row.manufacturer,
                "model": row.model,
                "serial_number": row.serial_number,
                "installed_at": row.installed_at,
                "status": row.status,
                "notes": row.notes,
                "is_active": row.is_active,
            }
        )
    elif resource == IntegrationResource.VISIT_PLANS:
        payload.update(
            {
                "station_id": row.station_id,
                "technician_membership_id": row.technician_membership_id,
                "checklist_template_id": row.checklist_template_id,
                "frequency_days": row.frequency_days,
                "start_at": row.start_at,
                "end_at": row.end_at,
                "next_due_at": row.next_due_at,
                "is_active": row.is_active,
                "notes": row.notes,
            }
        )
    elif resource == IntegrationResource.VISITS:
        payload.update(
            {
                "visit_plan_id": row.visit_plan_id,
                "station_id": row.station_id,
                "technician_membership_id": row.technician_membership_id,
                "checklist_template_id": row.checklist_template_id,
                "scheduled_for": row.scheduled_for,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "status": row.status,
                "notes": row.notes,
            }
        )
    elif resource == IntegrationResource.MEASUREMENTS:
        payload.update(
            {
                "visit_id": row.visit_id,
                "measurement_type": row.measurement_type,
                "status": row.status,
                "value": row.value,
                "unit": row.unit,
                "reason": row.reason,
                "measured_at": row.measured_at,
            }
        )
    elif resource == IntegrationResource.OCCURRENCES:
        payload.update(
            {
                "visit_id": row.visit_id,
                "station_id": row.station_id,
                "asset_id": row.asset_id,
                "occurrence_type": row.occurrence_type,
                "severity": row.severity,
                "status": row.status,
                "description": row.description,
                "detected_at": row.detected_at,
                "created_by_user_id": row.created_by_user_id,
            }
        )
    elif resource == IntegrationResource.WORK_ORDERS:
        payload.update(
            {
                "occurrence_id": row.occurrence_id,
                "station_id": row.station_id,
                "asset_id": row.asset_id,
                "assigned_membership_id": row.assigned_membership_id,
                "priority": row.priority,
                "status": row.status,
                "description": row.description,
                "sla_due_at": row.sla_due_at,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "validated_at": row.validated_at,
            }
        )
    elif resource == IntegrationResource.WORK_ORDER_HISTORY:
        payload = {
            "id": row.id,
            "work_order_id": row.work_order_id,
            "from_status": row.from_status,
            "to_status": row.to_status,
            "changed_by_user_id": row.changed_by_user_id,
            "note": row.note,
            "changed_at": row.changed_at,
        }
    elif resource == IntegrationResource.REVIEWS:
        payload = {
            "id": row.id,
            "visit_id": row.visit_id,
            "reviewer_user_id": row.reviewer_user_id,
            "decision": row.decision,
            "notes": row.notes,
            "reviewed_at": row.reviewed_at,
        }
    else:
        raise ValueError(f"unsupported integration resource: {resource}")

    return payload


_RESOURCE_CONFIG = {
    IntegrationResource.CLIENTS: (Client, Client.updated_at),
    IntegrationResource.DEVELOPMENTS: (Development, Development.updated_at),
    IntegrationResource.STATIONS: (Station, Station.updated_at),
    IntegrationResource.ASSETS: (Asset, Asset.updated_at),
    IntegrationResource.VISIT_PLANS: (VisitPlan, VisitPlan.updated_at),
    IntegrationResource.VISITS: (Visit, Visit.updated_at),
    IntegrationResource.MEASUREMENTS: (Measurement, Measurement.updated_at),
    IntegrationResource.OCCURRENCES: (Occurrence, Occurrence.updated_at),
    IntegrationResource.WORK_ORDERS: (WorkOrder, WorkOrder.updated_at),
    IntegrationResource.WORK_ORDER_HISTORY: (
        WorkOrderStatusHistory,
        WorkOrderStatusHistory.changed_at,
    ),
    IntegrationResource.REVIEWS: (VisitReview, VisitReview.reviewed_at),
}


async def export_resource(
    session: AsyncSession,
    context: IntegrationContext,
    resource: IntegrationResource,
    *,
    updated_since: datetime | None,
    snapshot_at: datetime | None,
    limit: int,
    offset: int,
) -> dict:
    now = datetime.now(UTC)
    if updated_since is not None and updated_since.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="updated_since_must_include_timezone",
        )
    if snapshot_at is not None and snapshot_at.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="snapshot_at_must_include_timezone",
        )
    if snapshot_at is not None and snapshot_at > now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="snapshot_at_cannot_be_future",
        )
    generated_at = snapshot_at or now
    model, watermark_column = _RESOURCE_CONFIG[resource]

    stmt = select(model).where(
        model.tenant_id == context.tenant_id,
        watermark_column <= generated_at,
    )
    if updated_since is not None:
        stmt = stmt.where(watermark_column > updated_since)

    stmt = (
        stmt.order_by(watermark_column, model.id)
        .limit(limit)
        .offset(offset)
    )
    rows = list((await session.execute(stmt)).scalars().all())

    return {
        "schema_version": "1",
        "tenant_id": context.tenant_id,
        "generated_at": generated_at,
        "items": [_serialize(resource, row) for row in rows],
    }
