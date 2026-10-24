from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile

from app.content import service
from app.content.common import hydrate, oid, public_menu, snapshot_for
from app.content.media import read_asset, upload_asset
from app.content.schemas import (
    Category,
    Localization,
    MenuCreate,
    MenuUpdate,
    POICreate,
    POIUpdate,
    Submission,
    SubmissionReview,
    language_code,
)
from app.content.sync import load_all
from app.core.audit import audit, public_document, read_snapshot, run_transaction
from app.core.database import get_db
from app.core.rbac import (
    require_any_permission,
    require_permission,
    require_verified_owner_permission,
)
from app.core.security import utcnow
from app.content.compat import router as compatibility_router

router = APIRouter()
public = APIRouter(prefix="/poi", tags=["content"])
admin = APIRouter(prefix="/admin", tags=["content-admin"])
owner = APIRouter(prefix="/owner", tags=["content-owner"])
media = APIRouter(prefix="/media", tags=["media"])
editor = require_permission("content.publish")


def locale(value):
    try:
        return language_code(value)
    except ValueError:
        raise HTTPException(422, "Invalid language code") from None


def query_alias(current, previous, default=None):
    if current is not None and previous is not None and current != previous:
        raise HTTPException(422, "Conflicting query parameter aliases")
    return (
        current
        if current is not None
        else previous
        if previous is not None
        else default
    )


async def owner_reader(actor=Depends(require_permission("content.read"))):
    if actor["realm"] != "admin_users":
        raise HTTPException(403, "Owner account required")
    return actor


@public.get("/ping")
async def ping_content():
    return {"lane": "content", "status": "ok"}


@public.get("/load-all")
async def sync_content(
    cursor: str | None = Query(None, max_length=4096),
    updated_after: datetime | None = None,
    language: str | None = Query(None, max_length=32),
    lang: str | None = Query(None, max_length=32, include_in_schema=False),
    limit: int | None = Query(None, ge=1, le=500),
    if_none_match: str | None = Header(None),
):
    return await load_all(
        cursor=cursor,
        updated_after=updated_after,
        language=query_alias(language, lang),
        limit=limit,
        if_none_match=if_none_match,
    )


@public.get("/nearby")
async def nearby(
    latitude: float | None = Query(None, ge=-90, le=90, allow_inf_nan=False),
    longitude: float | None = Query(None, ge=-180, le=180, allow_inf_nan=False),
    radius_m: float = Query(5000, ge=1, le=100000, allow_inf_nan=False),
    language: str | None = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=200),
    category: Category | None = None,
    lat: float | None = Query(
        None, ge=-90, le=90, allow_inf_nan=False, include_in_schema=False
    ),
    lng: float | None = Query(
        None, ge=-180, le=180, allow_inf_nan=False, include_in_schema=False
    ),
    lang: str | None = Query(None, max_length=32, include_in_schema=False),
):
    latitude, longitude = query_alias(latitude, lat), query_alias(longitude, lng)
    if latitude is None or longitude is None:
        raise HTTPException(422, "latitude/longitude (or lat/lng) are required")
    return await service.nearby(
        latitude,
        longitude,
        radius_m,
        locale(query_alias(language, lang, "vi")),
        limit,
        category,
    )


@public.get("/{poi_id}")
async def detail(poi_id: str, language: str = Query("vi", max_length=32)):
    async with read_snapshot() as session:
        poi = await service.get_poi(poi_id, session, public=True)
        return hydrate(await snapshot_for(poi, session), locale(language))


@public.post("", status_code=201)
async def create_poi(
    payload: POICreate,
    actor=Depends(require_permission("poi.create")),
    publisher=Depends(editor),
):
    return await service.create_poi(payload, actor)


@public.patch("/{poi_id}")
async def update_poi(
    poi_id: str,
    payload: POIUpdate,
    actor=Depends(require_permission("poi.update")),
    publisher=Depends(editor),
):
    return await service.update_poi(poi_id, payload, actor)


@public.delete("/{poi_id}", status_code=204)
async def delete_poi(
    poi_id: str,
    actor=Depends(require_permission("poi.delete")),
    publisher=Depends(editor),
):
    await service.delete_poi(poi_id, actor)


@public.get("/{poi_id}/menu-items")
async def public_menu_items(poi_id: str):
    async with read_snapshot() as session:
        await service.get_poi(poi_id, session, public=True)
        return [
            public_menu(row)
            async for row in get_db()["menu_items"]
            .find({"poi_id": poi_id, "is_available": True}, session=session)
            .sort("_id", 1)
        ]


@admin.get("/pois")
async def all_pois(
    limit: int = Query(50, ge=1, le=100),
    before: str | None = None,
    actor=Depends(require_permission("poi.read")),
    publisher=Depends(editor),
):
    query = {"_id": {"$lt": oid(before)}} if before else {}
    return [
        public_document(row)
        async for row in get_db()["pois"].find(query).sort("_id", -1).limit(limit)
    ]


@admin.get("/submissions")
async def submissions(
    status: Literal["pending", "approved", "rejected", "cancelled"] | None = None,
    limit: int = Query(50, ge=1, le=100),
    before: str | None = None,
    actor=Depends(editor),
):
    query = ({"status": status} if status else {}) | (
        {"_id": {"$lt": oid(before)}} if before else {}
    )
    return [
        public_document(row)
        async for row in get_db()["poi_submissions"]
        .find(query)
        .sort("_id", -1)
        .limit(limit)
    ]


@admin.patch("/submissions/{submission_id}")
async def review_submission(
    submission_id: str, payload: SubmissionReview, actor=Depends(editor)
):
    return await service.review(submission_id, payload, actor)


@owner.post("/submissions", status_code=201)
async def owner_submit(
    payload: Submission,
    actor=Depends(require_verified_owner_permission("content.submit")),
):
    return await service.submit(payload, actor)


@owner.get("/submissions")
async def own_submissions(
    limit: int = Query(50, ge=1, le=100),
    before: str | None = None,
    actor=Depends(owner_reader),
):
    query = {"owner_id": actor["sub"]} | (
        {"_id": {"$lt": oid(before)}} if before else {}
    )
    return [
        public_document(row)
        async for row in get_db()["poi_submissions"]
        .find(query)
        .sort("_id", -1)
        .limit(limit)
    ]


@owner.get("/pois")
async def own_pois(
    limit: int = Query(50, ge=1, le=100),
    before: str | None = None,
    actor=Depends(owner_reader),
):
    query = {"owner_id": actor["sub"]} | (
        {"_id": {"$lt": oid(before)}} if before else {}
    )
    return [
        public_document(row)
        async for row in get_db()["pois"].find(query).sort("_id", -1).limit(limit)
    ]


@owner.get("/notifications")
async def notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    before: str | None = None,
    actor=Depends(owner_reader),
):
    query = (
        {"owner_id": actor["sub"]}
        | ({"is_read": False} if unread_only else {})
        | ({"_id": {"$lt": oid(before)}} if before else {})
    )
    items = [
        public_document(row)
        async for row in get_db()["owner_notifications"]
        .find(query)
        .sort("_id", -1)
        .limit(limit)
    ]
    return {
        "items": items,
        "unread_count": await get_db()["owner_notifications"].count_documents(
            {"owner_id": actor["sub"], "is_read": False}
        ),
        "next_before": items[-1]["id"] if len(items) == limit else None,
    }


@owner.patch("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, actor=Depends(owner_reader)):
    async def operation(session):
        query = {"_id": oid(notification_id), "owner_id": actor["sub"]}
        row = await get_db()["owner_notifications"].find_one(query, session=session)
        if not row:
            raise HTTPException(404, "Notification not found")
        if not row["is_read"]:
            await get_db()["owner_notifications"].update_one(
                query, {"$set": {"is_read": True, "read_at": utcnow()}}, session=session
            )
            await audit(
                "notification.read",
                "owner_notifications",
                notification_id,
                actor,
                session=session,
            )
        return {"id": notification_id, "is_read": True}

    return await run_transaction(operation)


@owner.get("/pois/{poi_id}/menu-items")
async def own_menu_items(
    poi_id: str, actor=Depends(require_verified_owner_permission("menu.read"))
):
    async with read_snapshot() as session:
        await service.get_poi(poi_id, session, owner_id=actor["sub"])
        return [
            public_menu(row)
            async for row in get_db()["menu_items"]
            .find({"poi_id": poi_id}, session=session)
            .sort("_id", 1)
        ]


@owner.post("/menu-items", status_code=201)
async def owner_create_menu(
    payload: MenuCreate, actor=Depends(require_verified_owner_permission("menu.create"))
):
    return await service.menu_mutation(
        payload.poi_id, actor, payload=payload, owner=True
    )


@owner.patch("/pois/{poi_id}/menu-items/{item_id}")
async def owner_update_menu(
    poi_id: str,
    item_id: str,
    payload: MenuUpdate,
    actor=Depends(require_verified_owner_permission("menu.update")),
):
    return await service.menu_mutation(
        poi_id, actor, payload=payload, item_id=item_id, owner=True
    )


@owner.delete("/pois/{poi_id}/menu-items/{item_id}", status_code=204)
async def owner_delete_menu(
    poi_id: str,
    item_id: str,
    actor=Depends(require_verified_owner_permission("menu.delete")),
):
    await service.menu_mutation(
        poi_id, actor, item_id=item_id, deleting=True, owner=True
    )


@admin.post("/menu-items", status_code=201)
async def admin_create_menu(
    payload: MenuCreate,
    actor=Depends(require_permission("menu.create")),
    publisher=Depends(editor),
):
    return await service.menu_mutation(payload.poi_id, actor, payload=payload)


@admin.patch("/pois/{poi_id}/menu-items/{item_id}")
async def admin_update_menu(
    poi_id: str,
    item_id: str,
    payload: MenuUpdate,
    actor=Depends(require_permission("menu.update")),
    publisher=Depends(editor),
):
    return await service.menu_mutation(poi_id, actor, payload=payload, item_id=item_id)


@admin.delete("/pois/{poi_id}/menu-items/{item_id}", status_code=204)
async def admin_delete_menu(
    poi_id: str,
    item_id: str,
    actor=Depends(require_permission("menu.delete")),
    publisher=Depends(editor),
):
    await service.menu_mutation(poi_id, actor, item_id=item_id, deleting=True)


@admin.put("/pois/{poi_id}/localizations/{language}")
async def put_localization(
    poi_id: str,
    language: str,
    payload: Localization,
    actor=Depends(require_permission("content.update")),
    publisher=Depends(editor),
):
    language = locale(language)
    if language == "vi":
        raise HTTPException(422, "Vietnamese is the source; edit the POI instead")
    return await service.set_localization(poi_id, language, payload, actor)


@admin.delete("/pois/{poi_id}/localizations/{language}", status_code=204)
async def delete_localization(
    poi_id: str,
    language: str,
    actor=Depends(require_permission("content.delete")),
    publisher=Depends(editor),
):
    await service.set_localization(poi_id, locale(language), None, actor, deleting=True)


@owner.post("/media/images", status_code=201)
async def owner_upload_image(
    file: UploadFile = File(...),
    actor=Depends(require_verified_owner_permission("content.submit")),
):
    return await upload_asset(file, actor)


@admin.post("/media/images", status_code=201)
async def admin_upload_image(
    file: UploadFile = File(...),
    actor=Depends(require_any_permission("poi.create", "poi.update")),
    publisher=Depends(editor),
):
    return await upload_asset(file, actor)


@admin.post("/media/audio", status_code=201)
async def admin_upload_audio(
    file: UploadFile = File(...),
    actor=Depends(require_permission("content.update")),
    publisher=Depends(editor),
):
    return await upload_asset(file, actor, kind="audio")


@media.get("/{asset_id}")
async def public_media(asset_id: str):
    return await read_asset(asset_id)


@owner.get("/media/{asset_id}")
async def owner_media(asset_id: str, actor=Depends(owner_reader)):
    return await read_asset(asset_id, actor)


@admin.get("/media/{asset_id}")
async def admin_media(asset_id: str, actor=Depends(editor)):
    return await read_asset(asset_id, actor, editor=True)


@admin.get("/media-cleanup")
async def cleanup_jobs(
    limit: int = Query(50, ge=1, le=100),
    state: Literal["pending", "processing", "failed", "completed"] | None = None,
    actor=Depends(require_permission("system.read")),
):
    query = {"state": state} if state else {"state": {"$ne": "completed"}}
    return [
        public_document(row)
        async for row in get_db()["media_cleanup_jobs"]
        .find(query)
        .sort("_id", -1)
        .limit(limit)
    ]


@admin.post("/media-cleanup/{job_id}/retry")
async def retry_cleanup(
    job_id: str, actor=Depends(require_permission("system.update"))
):
    async def operation(session):
        result = await get_db()["media_cleanup_jobs"].update_one(
            {"_id": oid(job_id), "state": "failed"},
            {"$set": {"state": "pending", "attempts": 0, "run_after": utcnow()}},
            session=session,
        )
        if not result.modified_count:
            raise HTTPException(409, "Only failed cleanup jobs can be retried")
        await audit(
            "media.cleanup.retry", "media_cleanup_jobs", job_id, actor, session=session
        )
        return {"id": job_id, "state": "pending"}

    return await run_transaction(operation)


router.include_router(public)
router.include_router(admin)
router.include_router(owner)
router.include_router(media)
router.include_router(compatibility_router)
