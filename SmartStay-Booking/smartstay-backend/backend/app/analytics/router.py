from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/ping")
async def ping_analytics():
    return {"lane": "analytics", "status": "ok"}