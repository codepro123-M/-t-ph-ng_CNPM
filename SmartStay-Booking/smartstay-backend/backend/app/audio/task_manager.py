"""MongoDB-backed resumable audio jobs; leases and heartbeats survive worker restarts."""

import asyncio
import hashlib
import json
import logging
from contextlib import suppress
from datetime import timedelta

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from app.audio.service import PRIORITY_LANGUAGES
from app.content import service as content_service
from app.content.common import oid
from app.content.schemas import POIUpdate, language_code
from app.core.audit import audit, public_document, run_transaction
from app.core.config import (
    AUDIO_TASK_HEARTBEAT_SECONDS,
    AUDIO_TASK_RETENTION_DAYS,
    MAX_CONCURRENT_TTS,
)
from app.core.database import get_db
from app.core.security import random_id, utcnow
from app.localization.service import SYSTEM_ACTOR, localization_service

AUDIO_TASK_HEARTBEAT = AUDIO_TASK_HEARTBEAT_SECONDS
logger = logging.getLogger("smartstay.audio.jobs")
__all__ = ["AUDIO_TASK_HEARTBEAT", "MAX_CONCURRENT_TTS", "audio_task_manager"]


class TaskStopped(Exception):
    pass


class AudioTaskManager:
    async def ensure_indexes(self):
        db = get_db()
        await db["audio_tasks"].create_index([("status", 1), ("lease_until", 1)])
        await db["audio_tasks"].create_index([("poi_id", 1), ("source_revision", 1)])
        await db["audio_tasks"].create_index("expires_at", expireAfterSeconds=0)

    async def enqueue(
        self, poi_id, *, languages=None, activation_requested=False, actor=None
    ):
        poi = await content_service.get_poi(poi_id)
        languages = sorted(
            set(language_code(code) for code in (languages or PRIORITY_LANGUAGES))
        )
        if not 1 <= len(languages) <= 10:
            raise HTTPException(422, "Choose between 1 and 10 audio languages")
        if activation_requested and "en" not in languages:
            raise HTTPException(422, "Activation requires an English audio guide")
        key = json.dumps(
            [poi_id, poi["source_revision"], languages, activation_requested]
        )
        task_id = ObjectId(hashlib.sha256(key.encode()).hexdigest()[:24])
        stamp = utcnow()
        doc = {
            "_id": task_id,
            "poi_id": poi_id,
            "source_revision": poi["source_revision"],
            "languages": languages,
            "completed_languages": [],
            "status": "queued",
            "progress_pct": 0,
            "english_gate_passed": False,
            "activation_requested": activation_requested,
            "created_at": stamp,
            "updated_at": stamp,
            "last_heartbeat_at": stamp,
            "error": None,
        }

        async def operation(session):
            result = await get_db()["audio_tasks"].update_one(
                {"_id": task_id},
                {"$setOnInsert": {k: v for k, v in doc.items() if k != "_id"}},
                upsert=True,
                session=session,
            )
            if result.upserted_id:
                await audit(
                    "audio.enqueue", "audio_tasks", task_id, actor, session=session
                )
            return public_document(
                await get_db()["audio_tasks"].find_one(
                    {"_id": task_id}, session=session
                )
            )

        return await run_transaction(operation)

    async def _claim(self, task_id=None):
        now = utcnow()
        query = {
            "$or": [
                {"status": "queued"},
                {"status": "running", "lease_until": {"$lte": now}},
            ]
        }
        if task_id:
            query["_id"] = oid(task_id)
        return await get_db()["audio_tasks"].find_one_and_update(
            query,
            {
                "$set": {
                    "status": "running",
                    "claim_token": random_id(),
                    "lease_until": now + timedelta(seconds=180),
                    "last_heartbeat_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def _heartbeat(self, query):
        while True:
            await asyncio.sleep(AUDIO_TASK_HEARTBEAT)
            now = utcnow()
            await get_db()["audio_tasks"].update_one(
                query,
                {
                    "$set": {
                        "lease_until": now + timedelta(seconds=180),
                        "last_heartbeat_at": now,
                    }
                },
            )

    async def _run_claimed(self, task, *, one_language=None):
        query = {
            "_id": task["_id"],
            "claim_token": task["claim_token"],
            "status": "running",
        }
        heartbeat = asyncio.create_task(self._heartbeat(query))
        try:
            languages = (
                [one_language]
                if one_language
                else sorted(task["languages"], key=lambda code: (code != "en", code))
            )
            for language in languages:
                current = await get_db()["audio_tasks"].find_one(query)
                if not current:
                    raise TaskStopped()
                if language in current["completed_languages"]:
                    continue
                await localization_service.localize_single_poi(
                    task["poi_id"], language, source_revision=task["source_revision"]
                )
                if not await get_db()["audio_tasks"].find_one(query):
                    raise TaskStopped()
                if language == "en" and task["activation_requested"]:
                    poi = await content_service.get_poi(task["poi_id"])
                    if poi["source_revision"] != task["source_revision"]:
                        raise HTTPException(
                            409, "Source text changed; prepare a new audio task"
                        )
                    if not poi["is_active"]:
                        await content_service.update_poi(
                            task["poi_id"],
                            POIUpdate(
                                expected_revision=poi["revision"], is_active=True
                            ),
                            SYSTEM_ACTOR,
                        )
                changed = await get_db()["audio_tasks"].find_one_and_update(
                    query,
                    {
                        "$addToSet": {"completed_languages": language},
                        "$set": {
                            "updated_at": utcnow(),
                            **(
                                {"english_gate_passed": True}
                                if language == "en"
                                else {}
                            ),
                        },
                    },
                    return_document=ReturnDocument.AFTER,
                )
                if not changed:
                    raise TaskStopped()
                progress = round(
                    100 * len(changed["completed_languages"]) / len(task["languages"])
                )
                await get_db()["audio_tasks"].update_one(
                    query, {"$set": {"progress_pct": progress}}
                )
            current = await get_db()["audio_tasks"].find_one(query)
            if current:
                complete = len(current["completed_languages"]) == len(task["languages"])
                await get_db()["audio_tasks"].update_one(
                    query,
                    {
                        "$set": {
                            "status": "completed" if complete else "paused",
                            "error": None,
                            "updated_at": utcnow(),
                            **(
                                {
                                    "expires_at": utcnow()
                                    + timedelta(days=AUDIO_TASK_RETENTION_DAYS)
                                }
                                if complete
                                else {}
                            ),
                        },
                        "$unset": {"claim_token": "", "lease_until": ""},
                    },
                )
        except TaskStopped:
            pass
        except asyncio.CancelledError:
            await get_db()["audio_tasks"].update_one(
                query,
                {
                    "$set": {"status": "queued", "updated_at": utcnow()},
                    "$unset": {"claim_token": "", "lease_until": ""},
                },
            )
            raise
        except Exception as exc:
            message = (
                exc.detail
                if isinstance(exc, HTTPException)
                else "Audio preparation failed; retry the task"
            )
            await get_db()["audio_tasks"].update_one(
                query,
                {
                    "$set": {
                        "status": "failed",
                        "error": message,
                        "updated_at": utcnow(),
                    },
                    "$unset": {"claim_token": "", "lease_until": ""},
                },
            )
            logger.warning("Audio task failed (%s)", type(exc).__name__)
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
        return public_document(
            await get_db()["audio_tasks"].find_one({"_id": task["_id"]})
        )

    async def run_task(self, task_id, *, one_language=None):
        task = await self._claim(task_id)
        if task is None:
            raise HTTPException(409, "Task is not queued or is already running")
        if one_language and one_language not in task["languages"]:
            await self.control(task_id, "pause", SYSTEM_ACTOR)
            raise HTTPException(422, "Language is not part of this task")
        return await self._run_claimed(task, one_language=one_language)

    async def control(self, task_id, action, actor):
        states = {
            "pause": ("paused", ["queued", "running"]),
            "resume": ("queued", ["paused", "failed"]),
            "cancel": ("cancelled", ["queued", "running", "paused", "failed"]),
        }
        if action not in states:
            raise HTTPException(422, "Use pause, resume or cancel")
        state, allowed = states[action]

        async def operation(session):
            task = await get_db()["audio_tasks"].find_one_and_update(
                {"_id": oid(task_id), "status": {"$in": allowed}},
                {
                    "$set": {"status": state, "updated_at": utcnow(), "error": None},
                    "$unset": {"claim_token": "", "lease_until": ""},
                },
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if task is None:
                raise HTTPException(
                    409, "Task state changed or the action is not allowed"
                )
            await audit(
                "audio." + action, "audio_tasks", task_id, actor, session=session
            )
            return public_document(task)

        return await run_transaction(operation)

    async def worker_loop(self):
        while True:
            try:
                task = await self._claim()
                if task:
                    await self._run_claimed(task)
                    continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Audio worker will retry (%s)", type(exc).__name__)
            await asyncio.sleep(1)


audio_task_manager = AudioTaskManager()
