import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response, StreamingResponse
from pydantic import Field

from app.auth.schemas import StrictModel
from app.audio.service import PRIORITY_LANGUAGES, tts_service
from app.audio.task_manager import AUDIO_TASK_HEARTBEAT, audio_task_manager
from app.content.common import oid
from app.content.schemas import language_code
from app.core.audit import public_document
from app.core.database import get_db
from app.core.rbac import require_permission

router = APIRouter(tags=["audio"])
public = APIRouter(prefix="/audio")
editor = require_permission("content.publish")


class SpeechRequest(StrictModel):
    text: str = Field(min_length=1, max_length=20000)
    lang: str = Field(default="vi", max_length=32)
    translate_from: str | None = None


class AudioJob(StrictModel):
    poi_id: str
    languages: list[str] = Field(
        default_factory=lambda: list(PRIORITY_LANGUAGES), min_length=1, max_length=10
    )
    activation_requested: bool = False


@public.get("/languages")
async def languages():
    return {"languages": ["vi", "en", "zh", "ja", "ko"]}


@public.get("/voices")
async def voices(force_refresh: bool = False):
    return tts_service.get_voice_catalog(force_refresh)


@public.post("/tts")
async def speech(payload: SpeechRequest, actor=Depends(editor)):
    try:
        language = language_code(payload.lang)
        source = (
            language_code(payload.translate_from)
            if payload.translate_from
            else language
        )
    except ValueError:
        raise HTTPException(422, "Invalid language code") from None
    text = await tts_service.translate_text(payload.text, language, source)
    audio = await tts_service.synthesize_mp3(text, language)
    return Response(
        audio["audio_bytes"],
        media_type="audio/mpeg",
        headers={
            "X-Cache": "HIT" if audio["cache_hit"] else "MISS",
            "X-Audio-Voice": audio["voice"],
            "X-Audio-SHA256": audio["sha256"],
            "Cache-Control": "no-store",
        },
    )


@public.get("/pack-manifest")
async def pack_manifest(lang: str = Query("en", max_length=32)):
    try:
        lang = language_code(lang)
    except ValueError:
        raise HTTPException(422, "Invalid language code") from None
    db, files = get_db(), []
    async for poi in db["pois"].find({"is_active": True}).sort("_id", 1).limit(1000):
        row = (
            poi
            if lang == "vi"
            else await db["poi_localizations"].find_one(
                {
                    "poi_id": str(poi["_id"]),
                    "language": lang,
                    "source_revision": poi["source_revision"],
                }
            )
        )
        asset_id = (row or {}).get("audio_asset_id")
        if not asset_id:
            continue
        asset = await db["media_assets"].find_one(
            {"_id": oid(asset_id), "state": "ready", "kind": "audio", "is_public": True}
        )
        if asset:
            files.append(
                {
                    "poi_id": str(poi["_id"]),
                    "filename": asset_id + ".mp3",
                    "size_bytes": asset["size_bytes"],
                    "sha256": asset["sha256"],
                    "audio_url": "/media/" + asset_id,
                }
            )
    signature = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[
        :16
    ]
    return {
        "lang": lang,
        "pack_version": "pack-" + lang + "-" + signature,
        "total_files": len(files),
        "total_bytes": sum(row["size_bytes"] for row in files),
        "files": files,
        "limit": 1000,
    }


@router.get("/admin/audio-tasks")
async def tasks(actor=Depends(editor)):
    rows = [
        public_document(row)
        async for row in get_db()["audio_tasks"]
        .find({}, {"claim_token": 0})
        .sort("updated_at", -1)
        .limit(100)
    ]
    return {
        "items": rows,
        "total": await get_db()["audio_tasks"].count_documents({}),
        "heartbeat_interval_sec": AUDIO_TASK_HEARTBEAT,
    }


@router.post("/admin/audio-tasks", status_code=202)
async def enqueue(payload: AudioJob, actor=Depends(editor)):
    try:
        return await audio_task_manager.enqueue(
            payload.poi_id,
            languages=payload.languages,
            activation_requested=payload.activation_requested,
            actor=actor,
        )
    except ValueError:
        raise HTTPException(422, "Invalid language code") from None


async def task_events(request):
    previous, ticks = None, 0
    while not await request.is_disconnected():
        rows = [
            public_document(row)
            async for row in get_db()["audio_tasks"]
            .find({}, {"claim_token": 0})
            .sort("updated_at", -1)
            .limit(100)
        ]
        snapshot = json.dumps(jsonable_encoder(rows), sort_keys=True)
        if snapshot != previous:
            event = "snapshot" if previous is None else "update"
            yield "event: " + event + "\ndata: " + snapshot + "\n\n"
            previous = snapshot
        if ticks % AUDIO_TASK_HEARTBEAT == 0:
            yield "event: heartbeat\ndata: {}\n\n"
        ticks += 1
        await asyncio.sleep(1)


@router.get("/admin/audio-tasks/stream")
async def stream(request: Request, actor=Depends(editor)):
    return StreamingResponse(
        task_events(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/admin/audio-tasks/{task_id}/{action}")
async def control(task_id: str, action: str, actor=Depends(editor)):
    if action == "step-english":
        return await audio_task_manager.run_task(task_id, one_language="en")
    return await audio_task_manager.control(task_id, action, actor)


router.include_router(public)
router.include_router(public, prefix="/api/v1", include_in_schema=False)
