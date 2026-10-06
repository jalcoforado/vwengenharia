from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/status", tags=["system"])
async def status() -> dict[str, str]:
    return {"status": "ok", "service": "vwengenharia-api"}
