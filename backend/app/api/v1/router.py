from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.core_registers.router import router as core_registers_router
from app.modules.field.router import router as field_router
from app.modules.integration.router import router as integration_router
from app.modules.maintenance.router import router as maintenance_router
from app.modules.operations.router import router as operations_router
from app.modules.team.router import router as team_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(core_registers_router)
api_router.include_router(field_router)
api_router.include_router(integration_router)
api_router.include_router(maintenance_router)
api_router.include_router(operations_router)
api_router.include_router(team_router)


@api_router.get("/status", tags=["system"])
async def status() -> dict[str, str]:
    return {"status": "ok", "service": "vwengenharia-api"}
