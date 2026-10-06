from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.core_registers.service import add_audit
from app.modules.legacy_migration.parser import stage_workbook
from app.modules.legacy_migration.schemas import (
    AutoMapResponse,
    LegacyMigrationSummary,
    MaterializeRequest,
    MaterializeResponse,
    StageWorkbookResponse,
    StationMappingUpsert,
    TechnicianMappingUpsert,
)
from app.modules.legacy_migration.service import (
    auto_map_exact,
    materialize_legacy_visits,
    migration_summary,
    upsert_station_mapping,
    upsert_technician_mapping,
)

router = APIRouter(prefix="/legacy-migration", tags=["migracao"])

ADMIN_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
)
AdminContextDep = Annotated[AuthContext, Depends(require_roles(*ADMIN_ROLES))]

MAX_UPLOAD_BYTES = 25_000_000


@router.get("/summary", response_model=LegacyMigrationSummary)
async def get_migration_summary(
    context: AdminContextDep,
    session: SessionDep,
) -> LegacyMigrationSummary:
    return LegacyMigrationSummary.model_validate(
        await migration_summary(session, context)
    )


@router.post("/stage", response_model=StageWorkbookResponse)
async def post_stage_workbook(
    context: AdminContextDep,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    sheet: Annotated[str, Form()] = "Página1",
) -> StageWorkbookResponse:
    filename = file.filename or "legacy.xlsx"
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="xlsx_required",
        )

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file_too_large",
        )

    try:
        result = await stage_workbook(
            session,
            tenant_id=context.tenant.id,
            filename=filename,
            content=content,
            sheet_name=sheet,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    add_audit(
        session,
        context,
        action="LEGACY_WORKBOOK_STAGE",
        entity_type="legacy_migration",
        entity_id=context.tenant.id,
        fields=[
            f"file:{filename}",
            f"staged:{result['staged']}",
            f"errors:{result['errors']}",
        ],
    )
    await session.commit()
    return StageWorkbookResponse.model_validate(result)


@router.post("/map-station", status_code=status.HTTP_204_NO_CONTENT)
async def post_station_mapping(
    payload: StationMappingUpsert,
    context: AdminContextDep,
    session: SessionDep,
) -> Response:
    await upsert_station_mapping(
        session,
        context,
        source_label=payload.source_label,
        station_id=payload.station_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/map-technician", status_code=status.HTTP_204_NO_CONTENT)
async def post_technician_mapping(
    payload: TechnicianMappingUpsert,
    context: AdminContextDep,
    session: SessionDep,
) -> Response:
    await upsert_technician_mapping(
        session,
        context,
        source_label=payload.source_label,
        membership_id=payload.membership_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auto-map", response_model=AutoMapResponse)
async def post_auto_map(
    context: AdminContextDep,
    session: SessionDep,
) -> AutoMapResponse:
    return AutoMapResponse.model_validate(
        await auto_map_exact(session, context)
    )


@router.post("/materialize", response_model=MaterializeResponse)
async def post_materialize(
    payload: MaterializeRequest,
    context: AdminContextDep,
    session: SessionDep,
) -> MaterializeResponse:
    return MaterializeResponse.model_validate(
        await materialize_legacy_visits(
            session,
            context,
            limit=payload.limit,
            preserve_source_review_status=payload.preserve_source_review_status,
        )
    )
