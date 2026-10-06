import re

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import Visit, VisitStatus
from app.models.identity import Membership, Role
from app.models.legacy import (
    LegacyStationMapping,
    LegacyTechnicianMapping,
    LegacyVisitStage,
)
from app.models.operations import Station
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit, tenant_get_or_404

FIELD_ROLES = {Role.TECNICO.value, Role.MANUTENCAO.value}


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


async def migration_summary(
    session: AsyncSession,
    context: AuthContext,
) -> dict:
    tenant_id = context.tenant.id
    grouped = dict(
        (
            await session.execute(
                select(
                    LegacyVisitStage.status,
                    func.count(LegacyVisitStage.id),
                )
                .where(LegacyVisitStage.tenant_id == tenant_id)
                .group_by(LegacyVisitStage.status)
            )
        ).all()
    )
    total = sum(int(value) for value in grouped.values())

    station_mapped = set(
        (
            await session.execute(
                select(LegacyStationMapping.source_label).where(
                    LegacyStationMapping.tenant_id == tenant_id
                )
            )
        ).scalars()
    )
    technician_mapped = set(
        (
            await session.execute(
                select(LegacyTechnicianMapping.source_label).where(
                    LegacyTechnicianMapping.tenant_id == tenant_id
                )
            )
        ).scalars()
    )

    station_labels = set(
        (
            await session.execute(
                select(LegacyVisitStage.station_label)
                .where(
                    LegacyVisitStage.tenant_id == tenant_id,
                    LegacyVisitStage.station_label.is_not(None),
                )
                .distinct()
            )
        ).scalars()
    )
    technician_labels = set(
        (
            await session.execute(
                select(LegacyVisitStage.technician_label)
                .where(
                    LegacyVisitStage.tenant_id == tenant_id,
                    LegacyVisitStage.technician_label.is_not(None),
                )
                .distinct()
            )
        ).scalars()
    )

    return {
        "total": total,
        "staged": int(grouped.get("STAGED", 0)),
        "imported": int(grouped.get("IMPORTED", 0)),
        "errors": int(grouped.get("ERROR", 0)),
        "unmapped": int(grouped.get("UNMAPPED", 0)),
        "unmapped_station_labels": sorted(station_labels - station_mapped),
        "unmapped_technician_labels": sorted(
            technician_labels - technician_mapped
        ),
    }


async def upsert_station_mapping(
    session: AsyncSession,
    context: AuthContext,
    *,
    source_label: str,
    station_id,
) -> LegacyStationMapping:
    await tenant_get_or_404(session, Station, context.tenant.id, station_id)
    label = source_label.strip()
    mapping = (
        await session.execute(
            select(LegacyStationMapping).where(
                LegacyStationMapping.tenant_id == context.tenant.id,
                LegacyStationMapping.source_label == label,
            )
        )
    ).scalar_one_or_none()
    if mapping is None:
        mapping = LegacyStationMapping(
            tenant_id=context.tenant.id,
            source_label=label,
            station_id=station_id,
        )
        session.add(mapping)
    else:
        mapping.station_id = station_id
    await session.commit()
    await session.refresh(mapping)
    return mapping


async def upsert_technician_mapping(
    session: AsyncSession,
    context: AuthContext,
    *,
    source_label: str,
    membership_id,
) -> LegacyTechnicianMapping:
    membership = await tenant_get_or_404(
        session, Membership, context.tenant.id, membership_id
    )
    if membership.role not in FIELD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="membership_is_not_field_role",
        )

    label = source_label.strip()
    mapping = (
        await session.execute(
            select(LegacyTechnicianMapping).where(
                LegacyTechnicianMapping.tenant_id == context.tenant.id,
                LegacyTechnicianMapping.source_label == label,
            )
        )
    ).scalar_one_or_none()
    if mapping is None:
        mapping = LegacyTechnicianMapping(
            tenant_id=context.tenant.id,
            source_label=label,
            membership_id=membership_id,
        )
        session.add(mapping)
    else:
        mapping.membership_id = membership_id
    await session.commit()
    await session.refresh(mapping)
    return mapping


async def auto_map_exact(
    session: AsyncSession,
    context: AuthContext,
) -> dict[str, int]:
    tenant_id = context.tenant.id

    stations = list(
        (
            await session.execute(
                select(Station).where(Station.tenant_id == tenant_id)
            )
        ).scalars()
    )
    station_by_name: dict[str, Station] = {}
    station_collisions: set[str] = set()
    for station in stations:
        key = normalize_label(station.name)
        if key in station_by_name:
            station_collisions.add(key)
        else:
            station_by_name[key] = station
    for key in station_collisions:
        station_by_name.pop(key, None)

    memberships = list(
        (
            await session.execute(
                select(Membership).where(
                    Membership.tenant_id == tenant_id,
                    Membership.is_active.is_(True),
                    Membership.role.in_(FIELD_ROLES),
                )
            )
        ).scalars()
    )
    from app.models.identity import User

    users = {
        user.id: user
        for user in (
            await session.execute(
                select(User).where(
                    User.id.in_([membership.user_id for membership in memberships])
                )
            )
        ).scalars()
    }
    membership_by_name: dict[str, Membership] = {}
    membership_collisions: set[str] = set()
    for membership in memberships:
        user = users.get(membership.user_id)
        if user is None:
            continue
        key = normalize_label(user.name)
        if key in membership_by_name:
            membership_collisions.add(key)
        else:
            membership_by_name[key] = membership
    for key in membership_collisions:
        membership_by_name.pop(key, None)

    summary = await migration_summary(session, context)
    stations_mapped = 0
    technicians_mapped = 0

    for label in summary["unmapped_station_labels"]:
        station = station_by_name.get(normalize_label(label))
        if station is not None:
            await upsert_station_mapping(
                session,
                context,
                source_label=label,
                station_id=station.id,
            )
            stations_mapped += 1

    for label in summary["unmapped_technician_labels"]:
        membership = membership_by_name.get(normalize_label(label))
        if membership is not None:
            await upsert_technician_mapping(
                session,
                context,
                source_label=label,
                membership_id=membership.id,
            )
            technicians_mapped += 1

    return {
        "stations_mapped": stations_mapped,
        "technicians_mapped": technicians_mapped,
    }


async def materialize_legacy_visits(
    session: AsyncSession,
    context: AuthContext,
    *,
    limit: int,
    preserve_source_review_status: bool,
) -> dict[str, int]:
    tenant_id = context.tenant.id
    stages = list(
        (
            await session.execute(
                select(LegacyVisitStage)
                .where(
                    LegacyVisitStage.tenant_id == tenant_id,
                    LegacyVisitStage.status.in_(["STAGED", "UNMAPPED"]),
                )
                .order_by(LegacyVisitStage.source_row)
                .limit(limit)
            )
        ).scalars()
    )

    station_mappings = {
        item.source_label: item.station_id
        for item in (
            await session.execute(
                select(LegacyStationMapping).where(
                    LegacyStationMapping.tenant_id == tenant_id
                )
            )
        ).scalars()
    }
    technician_mappings = {
        item.source_label: item.membership_id
        for item in (
            await session.execute(
                select(LegacyTechnicianMapping).where(
                    LegacyTechnicianMapping.tenant_id == tenant_id
                )
            )
        ).scalars()
    }

    imported = 0
    skipped_unmapped = 0
    errors = 0

    for stage in stages:
        station_id = station_mappings.get(stage.station_label or "")
        membership_id = technician_mappings.get(stage.technician_label or "")
        if station_id is None or membership_id is None:
            stage.status = "UNMAPPED"
            skipped_unmapped += 1
            continue
        if stage.scheduled_at is None:
            stage.status = "ERROR"
            stage.error_code = "INVALID_VISIT_DATETIME"
            stage.error_message = "Data de visita invalida no staging."
            errors += 1
            continue

        try:
            source_waiting = (
                (stage.source_status or "").strip().casefold()
                == "aguardando revisão".casefold()
            )
            visit_status = (
                VisitStatus.AGUARDANDO_REVISAO.value
                if preserve_source_review_status and source_waiting
                else VisitStatus.REVISADA.value
            )
            raw_notes = stage.raw_payload.get("Observações:")
            notes = (
                f"[LEGADO row={stage.source_row} status={stage.source_status or 'sem status'}]"
            )
            if raw_notes:
                notes += f" {raw_notes}"

            visit = Visit(
                tenant_id=tenant_id,
                station_id=station_id,
                technician_membership_id=membership_id,
                scheduled_for=stage.scheduled_at,
                finished_at=stage.scheduled_at,
                status=visit_status,
                notes=notes[:10000],
            )
            session.add(visit)
            await session.flush()
            stage.imported_visit_id = visit.id
            stage.status = "IMPORTED"
            stage.error_code = None
            stage.error_message = None
            imported += 1
        except (SQLAlchemyError, TypeError, ValueError) as exc:
            stage.status = "ERROR"
            stage.error_code = "MATERIALIZATION_ERROR"
            stage.error_message = str(exc)[:1000]
            errors += 1

    add_audit(
        session,
        context,
        action="LEGACY_VISITS_MATERIALIZE",
        entity_type="legacy_migration",
        entity_id=context.tenant.id,
        fields=[
            f"imported:{imported}",
            f"unmapped:{skipped_unmapped}",
            f"errors:{errors}",
        ],
    )
    await session.commit()

    return {
        "imported": imported,
        "skipped_unmapped": skipped_unmapped,
        "errors": errors,
    }
