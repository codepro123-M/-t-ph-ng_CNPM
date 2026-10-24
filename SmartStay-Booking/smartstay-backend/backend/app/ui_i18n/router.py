from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ui-bundles", tags=["ui_i18n"])


@router.get("/ping")
async def ping_ui_i18n():
    return {"lane": "ui_i18n", "status": "ok"}