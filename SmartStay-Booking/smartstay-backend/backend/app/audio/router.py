from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])


@router.get("/languages")
async def get_supported_languages():
    return {"languages": ["vi", "en", "zh", "ja", "ko"]}