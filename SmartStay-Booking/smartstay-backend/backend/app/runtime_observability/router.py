from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/runtime-observability", tags=["runtime_observability"])


@router.get("/ping")
async def ping_observability():
    return {"lane": "runtime_observability", "status": "ok"}