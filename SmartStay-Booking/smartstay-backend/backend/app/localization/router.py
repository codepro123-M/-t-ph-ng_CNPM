import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field, field_validator

from app.auth.schemas import StrictModel
from app.audio.task_manager import audio_task_manager
from app.content import service as content_service
from app.content.common import oid
from app.content.schemas import language_code
from app.core.database import get_db
from app.core.rbac import require_permission
from app.core.security import utcnow
from app.core.sessions import rate_limit
from app.localization.service import (
    HOTSET_MAX_POI_IDS,
    HOTSET_RADIUS_M,
    ON_DEMAND_RATE_LIMIT,
    localization_service,
)

router = APIRouter(tags=["localization"])
public = APIRouter(prefix="/localizations")


class OnDemand(StrictModel):
    poi_id: str
    lang: str = Field(max_length=32)
    validate_language = field_validator("lang")(language_code)


class Hotset(StrictModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    lang: str = Field(max_length=32)
    radius_m: float = Field(default=HOTSET_RADIUS_M, ge=1, le=HOTSET_RADIUS_M)
    poi_ids: list[str] | None = Field(default=None, max_length=HOTSET_MAX_POI_IDS)
    validate_language = field_validator("lang")(language_code)


class Warmup(StrictModel):
    lang: str = Field(max_length=32)
    validate_language = field_validator("lang")(language_code)


async def prepare(poi, language):
    cached = await localization_service.cached(poi, language)
    if cached:
        return {"status": "ready", **cached}
    task = await audio_task_manager.enqueue(str(poi["_id"]), languages=[language])
    if task["status"] == "failed":
        task = await audio_task_manager.control(
            task["id"], "resume", {"sub": "public-audio-retry", "realm": "system"}
        )
    return {
        "status": task["status"],
        "poi_id": str(poi["_id"]),
        "language": language,
        "task_id": task["id"],
        "error": task.get("error"),
    }


@public.post("/on-demand")
async def on_demand(payload: OnDemand, request: Request, response: Response):
    await rate_limit(request, "localization", limit=ON_DEMAND_RATE_LIMIT, seconds=600)
    poi = await content_service.get_poi(payload.poi_id, public=True)
    result = await prepare(poi, payload.lang)
    response.status_code = 200 if result["status"] == "ready" else 202
    response.headers["Cache-Control"] = "no-store"
    return result


@public.get("/poi/{poi_id}/status")
async def status(poi_id: str, lang: str = Query("en", max_length=32)):
    try:
        language = language_code(lang)
    except ValueError:
        raise HTTPException(422, "Invalid language code") from None
    poi = await content_service.get_poi(poi_id, public=True)
    cached = await localization_service.cached(poi, language)
    if cached:
        return {"status": "ready", **cached}
    task = await get_db()["audio_tasks"].find_one(
        {
            "poi_id": poi_id,
            "source_revision": poi["source_revision"],
            "languages": language,
        },
        sort=[("updated_at", -1)],
    )
    return {
        "poi_id": poi_id,
        "language": language,
        "status": task["status"] if task else "not_started",
        "progress_pct": task.get("progress_pct", 0) if task else 0,
        "error": task.get("error") if task else None,
    }


@public.post("/prepare-hotset", status_code=202)
async def hotset(payload: Hotset, request: Request):
    await rate_limit(request, "hotset", limit=30, seconds=600)
    nearby = await content_service.nearby(
        payload.lat, payload.lng, payload.radius_m, "vi", HOTSET_MAX_POI_IDS
    )
    selected = [
        row
        for row in nearby["items"]
        if not payload.poi_ids or row["id"] in payload.poi_ids
    ]
    jobs = [
        await prepare(
            await content_service.get_poi(row["id"], public=True), payload.lang
        )
        for row in selected
    ]
    return {
        "lang": payload.lang,
        "max_poi_ids": HOTSET_MAX_POI_IDS,
        "radius_m": payload.radius_m,
        "prepared_count": sum(row["status"] == "ready" for row in jobs),
        "queued_count": sum(row["status"] != "ready" for row in jobs),
        "items": jobs,
    }


async def warmup_status(language):
    job = await get_db()["warmup_jobs"].find_one({"_id": language})
    if not job:
        return {
            "lang": language,
            "status": "not_started",
            "total_pois": 0,
            "completed_pois": 0,
            "progress_pct": 0,
        }
    ids = [oid(value) for value in job["task_ids"]]
    total = len(ids)
    completed = await get_db()["audio_tasks"].count_documents(
        {"_id": {"$in": ids}, "status": "completed"}
    )
    failed = await get_db()["audio_tasks"].count_documents(
        {"_id": {"$in": ids}, "status": {"$in": ["failed", "cancelled"]}}
    )
    return {
        "lang": language,
        "status": "completed"
        if completed == total
        else "failed"
        if failed
        else "running",
        "total_pois": total,
        "completed_pois": completed,
        "failed_pois": failed,
        "progress_pct": round(100 * completed / total) if total else 100,
    }


@public.post("/warmup", status_code=202)
async def warmup(payload: Warmup, actor=Depends(require_permission("content.publish"))):
    pois = (
        await get_db()["pois"]
        .find({"is_active": True})
        .sort("_id", 1)
        .limit(1001)
        .to_list(length=1001)
    )
    if len(pois) > 1000:
        raise HTTPException(413, "Warmup supports up to 1000 properties per request")
    signature = hashlib.sha256(
        json.dumps([(str(row["_id"]), row["source_revision"]) for row in pois]).encode()
    ).hexdigest()
    old = await get_db()["warmup_jobs"].find_one({"_id": payload.lang})
    jobs = [
        await audio_task_manager.enqueue(
            str(row["_id"]), languages=[payload.lang], actor=actor
        )
        for row in pois
    ]
    await get_db()["warmup_jobs"].update_one(
        {"_id": payload.lang},
        {
            "$set": {
                "task_ids": [row["id"] for row in jobs],
                "signature": signature,
                "updated_at": utcnow(),
            }
        },
        upsert=True,
    )
    return {
        **await warmup_status(payload.lang),
        "idempotent_reused": bool(old and old["signature"] == signature),
    }


@public.get("/warmup/{lang}/status")
async def get_warmup(lang: str, actor=Depends(require_permission("content.publish"))):
    try:
        lang = language_code(lang)
    except ValueError:
        raise HTTPException(422, "Invalid language code") from None
    return await warmup_status(lang)


router.include_router(public)
router.include_router(public, prefix="/api/v1", include_in_schema=False)
