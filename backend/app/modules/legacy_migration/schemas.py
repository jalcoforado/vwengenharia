from uuid import UUID

from pydantic import BaseModel, Field


class LegacyMigrationSummary(BaseModel):
    total: int
    staged: int
    imported: int
    errors: int
    unmapped: int
    unmapped_station_labels: list[str]
    unmapped_technician_labels: list[str]


class StationMappingUpsert(BaseModel):
    source_label: str = Field(min_length=1, max_length=255)
    station_id: UUID


class TechnicianMappingUpsert(BaseModel):
    source_label: str = Field(min_length=1, max_length=255)
    membership_id: UUID


class AutoMapResponse(BaseModel):
    stations_mapped: int
    technicians_mapped: int


class MaterializeRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)
    preserve_source_review_status: bool = False


class MaterializeResponse(BaseModel):
    imported: int
    skipped_unmapped: int
    errors: int
