from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/localizations", tags=["localization"])


@router.get("/ping")
async def ping_localization():
    return {"lane": "localization", "status": "ok"}