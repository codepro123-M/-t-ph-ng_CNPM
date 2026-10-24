from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ai", tags=["ai_advisor"])


@router.get("/ping")
async def ping_ai():
    return {"lane": "ai_advisor", "status": "ok"}