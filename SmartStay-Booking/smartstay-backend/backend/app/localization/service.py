"""Build real translations and attach validated MP3 assets to canonical POI records."""

import io
from weakref import WeakValueDictionary
import asyncio

from bson import ObjectId
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from app.audio.service import tts_service
from app.content import service as content_service
from app.content.common import next_version, record_change
from app.content.media import queue_cleanup, touch_assets, upload_asset
from app.core.audit import audit, run_transaction
from app.core.database import get_db
from app.core.security import utcnow

HOTSET_MAX_POI_IDS = 10
HOTSET_RADIUS_M = 1500
ON_DEMAND_RATE_LIMIT = 30
SYSTEM_ACTOR = {"sub": "localization-worker", "realm": "system"}


class LocalizationService:
    def __init__(self):
        self._locks = WeakValueDictionary()

    async def cached(self, poi, language):
        db = get_db()
        if language == "vi":
            row = poi
        else:
            row = await db["poi_localizations"].find_one(
                {
                    "poi_id": str(poi["_id"]),
                    "language": language,
                    "source_revision": poi["source_revision"],
                }
            )
        asset_id = (row or {}).get("audio_asset_id")
        if not asset_id:
            return None
        asset = await db["media_assets"].find_one(
            {"_id": ObjectId(asset_id), "state": "ready", "kind": "audio"}
        )
        if not asset:
            return None
        return {
            "poi_id": str(poi["_id"]),
            "language": language,
            "audio_url": "/media/" + asset_id,
            "cache_hit": True,
        }

    async def localize_single_poi(
        self, poi_id, language, *, source_revision=None, actor=None
    ):
        actor = actor or SYSTEM_ACTOR
        key = poi_id + ":" + language
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        async with lock:
            poi = await content_service.get_poi(poi_id)
            revision = poi["source_revision"]
            if source_revision is not None and revision != source_revision:
                raise HTTPException(
                    409, "Source text changed; prepare a new audio task"
                )
            cached = await self.cached(poi, language)
            if cached:
                return cached
            texts = {}
            existing = await get_db()["poi_localizations"].find_one(
                {"poi_id": poi_id, "language": language, "source_revision": revision}
            )
            for field in ("name", "description", "check_in_instructions"):
                texts[field] = (
                    existing[field]
                    if existing and field in existing
                    else await tts_service.translate_text(
                        poi[field], target_lang=language, source_lang="vi"
                    )
                )
            script = ". ".join(value for value in texts.values() if value.strip())
            audio = await tts_service.synthesize_mp3(script, language)
            file = UploadFile(
                io.BytesIO(audio["audio_bytes"]),
                filename="narration.mp3",
                headers=Headers({"content-type": "audio/mpeg"}),
            )
            asset = await upload_asset(file, actor, kind="audio")
            if language == "vi":

                async def attach(session):
                    current = await content_service.get_poi(poi_id, session)
                    if current["source_revision"] != revision:
                        raise HTTPException(
                            409, "Source text changed; prepare a new audio task"
                        )
                    await touch_assets(
                        [asset["id"]],
                        session,
                        kind="audio",
                        publish=current["is_active"],
                    )
                    if current.get("audio_asset_id"):
                        await queue_cleanup(
                            [current["audio_asset_id"]],
                            session,
                            reason="audio_replaced",
                        )
                    version, stamp = await next_version(session)
                    changes = {
                        "audio_asset_id": asset["id"],
                        "revision": current["revision"] + 1,
                        "updated_at": stamp,
                    }
                    await get_db()["pois"].update_one(
                        {"_id": current["_id"]}, {"$set": changes}, session=session
                    )
                    await record_change(current | changes, version, stamp, session)
                    await audit("audio.attach", "pois", poi_id, actor, session=session)

                await run_transaction(attach)
            else:
                from app.content.schemas import Localization

                payload = Localization(
                    **texts, source_revision=revision, audio_asset_id=asset["id"]
                )
                await content_service.set_localization(poi_id, language, payload, actor)
            return {
                "poi_id": poi_id,
                "language": language,
                "audio_url": asset["url"],
                "cache_hit": audio["cache_hit"],
                "voice": audio["voice"],
                "updated_at": utcnow(),
            }


localization_service = LocalizationService()
