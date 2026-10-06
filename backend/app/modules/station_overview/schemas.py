from pydantic import BaseModel

from app.modules.core_registers.schemas import AssetRead, StationRead
from app.modules.field.schemas import VisitRead
from app.modules.maintenance.schemas import MaintenancePlanRead
from app.modules.materials.schemas import MaterialRequestRead
from app.modules.operations.schemas import OccurrenceRead, WorkOrderRead


class StationOverviewSummary(BaseModel):
    active_assets: int
    unavailable_assets: int
    open_occurrences: int
    open_work_orders: int
    overdue_work_orders: int
    overdue_maintenance: int
    open_material_requests: int


class StationOverviewResponse(BaseModel):
    station: StationRead
    summary: StationOverviewSummary
    assets: list[AssetRead]
    visits: list[VisitRead]
    occurrences: list[OccurrenceRead]
    work_orders: list[WorkOrderRead]
    maintenance_plans: list[MaintenancePlanRead]
    material_requests: list[MaterialRequestRead]
