from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/maps", tags=["maps"])


@router.get("/offline-options")
async def get_offline_map_options():
    return {"packs": []}