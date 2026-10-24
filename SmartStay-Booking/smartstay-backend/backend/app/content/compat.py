"""Explicit legacy URL adapters; all writes use the same transactional services.

Old arbitrary media URLs and the built-in demo administrator are intentionally
not accepted. Canonical schemas and permission checks remain authoritative.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field, model_validator

from app.admin.router import permissions
from app.auth.router import me
from app.content import service
from app.content.common import public_menu
from app.content.schemas import Localization, MenuCreate, MenuData, language_code
from app.core.audit import read_snapshot
from app.core.database import get_db
from app.core.rbac import (
    require_permission,
    require_verified_owner_permission,
)

router = APIRouter(tags=["compatibility"])


class LegacyLocalization(Localization):
    lang: str = Field(min_length=2, max_length=32)
    check_in_instructions: str = Field(default="", max_length=10000)
    audio_url: str | None = None

    @model_validator(mode="after")
    def managed_audio_only(self):
        if self.audio_url:
            raise ValueError("Upload MP3 and send audio_asset_id instead of audio_url")
        return self


@router.get("/content/ping", include_in_schema=False)
async def legacy_ping():
    return {"lane": "content", "status": "ok"}


@router.get("/admin/rbac/permissions", include_in_schema=False)
async def legacy_permissions(actor=Depends(require_permission("role.read"))):
    return await permissions(actor)


@router.get("/admin/me", include_in_schema=False)
async def legacy_admin_me(profile=Depends(me)):
    return profile


@router.get("/poi/{poi_id}/menu", include_in_schema=False)
async def legacy_public_menu(poi_id: str):
    async with read_snapshot() as session:
        await service.get_poi(poi_id, session, public=True)
        items = [
            public_menu(row)
            async for row in get_db()["menu_items"]
            .find({"poi_id": poi_id, "is_available": True}, session=session)
            .sort("_id", 1)
        ]
        return {"poi_id": poi_id, "total": len(items), "items": items}


@router.post("/owner/poi/{poi_id}/menu-items", status_code=201, include_in_schema=False)
async def legacy_create_menu(
    poi_id: str,
    payload: MenuData,
    actor=Depends(require_verified_owner_permission("menu.create")),
):
    return await service.menu_mutation(
        poi_id,
        actor,
        payload=MenuCreate(**payload.model_dump(), poi_id=poi_id),
        owner=True,
    )


@router.put("/poi/{poi_id}/localizations", include_in_schema=False)
async def legacy_localization(
    poi_id: str,
    payload: LegacyLocalization,
    actor=Depends(require_permission("content.update")),
    publisher=Depends(require_permission("content.publish")),
):
    try:
        language = language_code(payload.lang)
    except ValueError:
        raise HTTPException(422, "Invalid language code") from None
    if language == "vi":
        raise HTTPException(422, "Vietnamese is the POI source language")
    localization = Localization.model_validate(
        payload.model_dump(exclude={"lang", "audio_url"})
    )
    return await service.set_localization(poi_id, language, localization, actor)


@router.get("/compatibility/version", include_in_schema=False)
async def compatibility_version(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"storage": "mongodb", "content_schema": 1, "sync_cursor": "signed-v1"}
