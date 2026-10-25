"""Managed media with durable cleanup intents and fenced, idempotent deletion."""

import asyncio
import hashlib
import io
import json
import logging
import os
import subprocess
import tempfile
import warnings
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, UnidentifiedImageError
from pymongo import ReturnDocument
from starlette.concurrency import run_in_threadpool

from app.content.common import oid
from app.core.audit import audit, run_transaction
from app.core.config import MAX_IMAGE_SIZE_BYTES, settings
from app.core.database import get_db
from app.core.media_storage import create_s3_client
from app.core.security import utcnow

logger = logging.getLogger("smartstay.content.media")
FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


def inspect_image(data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as picture:
                if (
                    picture.format not in FORMATS
                    or picture.width * picture.height > 20_000_000
                    or getattr(picture, "n_frames", 1) != 1
                ):
                    raise ValueError("Unsupported image")
                mime, suffix = FORMATS[picture.format]
                width, height = picture.size
                picture.verify()
            with Image.open(io.BytesIO(data)) as picture:
                picture.load()
        return {
            "content_type": mime,
            "suffix": suffix,
            "width": width,
            "height": height,
        }
    except (
        UnidentifiedImageError,
        SyntaxError,
        EOFError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(
            415,
            "A valid JPEG, PNG or non-animated WebP image is required (maximum 20 megapixels)",
        ) from None


def inspect_audio(data):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name",
                "-show_entries",
                "format=format_name",
                "-of",
                "json",
                "pipe:0",
            ],
            input=data,
            capture_output=True,
            timeout=10,
            check=False,
        )
        parsed = json.loads(result.stdout) if result.returncode == 0 else {}
        if parsed.get("format", {}).get("format_name") != "mp3" or not any(
            row.get("codec_name") == "mp3" for row in parsed.get("streams", [])
        ):
            raise ValueError("Invalid MP3")
    except FileNotFoundError:
        raise HTTPException(
            503, "MP3 validation requires ffprobe (included in the Docker image)"
        ) from None
    except (subprocess.TimeoutExpired, ValueError):
        raise HTTPException(415, "A valid MP3 file is required") from None
    return {"content_type": "audio/mpeg", "suffix": ".mp3"}


def local_path(asset):
    root = Path(settings.CONTENT_MEDIA_DIR).resolve()
    path = (root / asset["object_key"]).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Invalid media path")
    return path


def s3_client_for(asset):
    if not settings.S3_ACCESS_KEY or not settings.S3_SECRET_KEY:
        raise RuntimeError("S3 credentials unavailable")
    return create_s3_client(
        settings.model_copy(
            update={"MEDIA_BACKEND": "s3", "S3_BUCKET": asset["bucket"]}
        )
    )


async def queue_cleanup(asset_ids, session, *, reason="content_removed"):
    now = utcnow()
    for asset_id in set(asset_ids):
        await get_db()["media_cleanup_jobs"].update_one(
            {"asset_id": asset_id},
            {
                "$set": {
                    "state": "pending",
                    "run_after": now
                    + timedelta(seconds=settings.CONTENT_MEDIA_GRACE_SECONDS),
                    "reason": reason,
                },
                "$setOnInsert": {
                    "asset_id": asset_id,
                    "created_at": now,
                    "attempts": 0,
                },
            },
            upsert=True,
            session=session,
        )


async def touch_assets(
    asset_ids, session, *, owner_id=None, existing=(), kind="image", publish=False
):
    for asset_id in set(asset_ids):
        row = await get_db()["media_assets"].find_one(
            {"_id": oid(asset_id), "state": "ready", "kind": kind}, session=session
        )
        if not row:
            raise HTTPException(
                422, "Media asset is missing, unavailable or has the wrong type"
            )
        if (
            owner_id is not None
            and row["owner_id"] != owner_id
            and asset_id not in existing
        ):
            raise HTTPException(403, "Cannot use another account's media")
        update = {"$inc": {"ref_revision": 1}}
        if publish:
            update["$set"] = {"is_public": True}
        result = await get_db()["media_assets"].update_one(
            {"_id": row["_id"], "state": "ready"}, update, session=session
        )
        if not result.modified_count:
            raise HTTPException(409, "Media changed concurrently; retry")


def write_blob(asset, data):
    if asset["storage_backend"] == "s3":
        with closing(s3_client_for(asset)) as client:
            result = client.put_object(
                Bucket=asset["bucket"],
                Key=asset["object_key"],
                Body=data,
                ContentType=asset["content_type"],
            )
        return {"version_id": result.get("VersionId")}
    path = local_path(asset)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return {"version_id": None}


async def upload_asset(file, actor, *, kind="image"):
    cap = MAX_IMAGE_SIZE_BYTES if kind == "image" else settings.MAX_AUDIO_SIZE_BYTES
    chunks, size = [], 0
    try:
        while chunk := await file.read(65536):
            size += len(chunk)
            if size > cap:
                raise HTTPException(
                    413,
                    "Image exceeds 5 MiB"
                    if kind == "image"
                    else "Audio exceeds the configured size limit",
                )
            chunks.append(chunk)
    finally:
        await file.close()
    data = b"".join(chunks)
    metadata = await run_in_threadpool(
        inspect_image if kind == "image" else inspect_audio, data
    )
    if file.content_type not in {
        metadata["content_type"],
        "application/octet-stream",
        None,
    }:
        raise HTTPException(415, "Declared MIME type does not match file contents")
    asset_id = ObjectId()
    suffix = metadata.pop("suffix")
    asset = metadata | {
        "_id": asset_id,
        "owner_id": actor["sub"],
        "owner_realm": actor["realm"],
        "kind": kind,
        "size_bytes": size,
        "sha256": hashlib.sha256(data).hexdigest(),
        "storage_backend": settings.MEDIA_BACKEND.lower(),
        "bucket": settings.S3_BUCKET,
        "object_key": f"content/{kind}/{asset_id}{suffix}",
        "state": "uploading",
        "is_public": False,
        "ref_revision": 0,
        "created_at": utcnow(),
    }

    async def reserve(session):
        await get_db()["media_assets"].insert_one(asset, session=session)
        await queue_cleanup([str(asset_id)], session, reason="orphan_upload")
        await audit("media.reserve", "media_assets", asset_id, actor, session=session)

    await run_transaction(reserve)
    try:
        storage = await run_in_threadpool(write_blob, asset, data)
    except Exception:
        # The pre-existing cleanup intent also covers ambiguous S3 PUT failures.
        raise HTTPException(
            503, "Media upload unavailable; its cleanup intent was retained"
        ) from None

    async def complete(session):
        result = await get_db()["media_assets"].update_one(
            {"_id": asset_id, "state": "uploading"},
            {"$set": storage | {"state": "ready"}},
            session=session,
        )
        if not result.modified_count:
            raise HTTPException(409, "Upload changed concurrently")
        await audit(
            "media.upload",
            "media_assets",
            asset_id,
            actor,
            session=session,
            details={"count": size},
        )

    await run_transaction(complete)
    return {
        "id": str(asset_id),
        "url": f"/media/{asset_id}",
        "preview_url": f"/owner/media/{asset_id}",
        "kind": kind,
        "size_bytes": size,
        **metadata,
    }


async def read_asset(asset_id, actor=None, *, editor=False):
    row = await get_db()["media_assets"].find_one(
        {"_id": oid(asset_id), "state": "ready"}
    )
    if not row or (
        not row["is_public"]
        and not editor
        and (
            not actor
            or actor["sub"] != row["owner_id"]
            or actor["realm"] != row["owner_realm"]
        )
    ):
        raise HTTPException(404, "Media not found")
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'",
        "ETag": '"' + row["sha256"] + '"',
        "Cache-Control": "public, max-age=3600, immutable"
        if row["is_public"] and actor is None
        else "no-store",
    }
    if row["storage_backend"] == "local":
        path = local_path(row)
        if not path.is_file():
            raise HTTPException(404, "Media not found")
        return FileResponse(path, media_type=row["content_type"], headers=headers)

    def open_stream():
        client = s3_client_for(row)
        try:
            args = {"Bucket": row["bucket"], "Key": row["object_key"]}
            if row.get("version_id"):
                args["VersionId"] = row["version_id"]
            result = client.get_object(**args)
            return client, result["Body"]
        except Exception:
            client.close()
            raise

    try:
        client, body = await run_in_threadpool(open_stream)
    except Exception:
        raise HTTPException(503, "Media storage unavailable") from None

    def chunks():
        try:
            while chunk := body.read(65536):
                yield chunk
        finally:
            body.close()
            client.close()

    return StreamingResponse(chunks(), media_type=row["content_type"], headers=headers)


async def has_references(asset_id, session):
    db = get_db()
    if await db["pois"].find_one(
        {"$or": [{"images": asset_id}, {"audio_asset_id": asset_id}]}, session=session
    ):
        return True
    if await db["poi_submissions"].find_one(
        {"status": "pending", "payload.images": asset_id}, session=session
    ):
        return True
    return bool(
        await db["poi_localizations"].find_one(
            {"audio_asset_id": asset_id}, session=session
        )
    )


def delete_blob(asset):
    if asset["storage_backend"] == "local":
        local_path(asset).unlink(missing_ok=True)
        return
    with closing(s3_client_for(asset)) as client:
        arguments = {"Bucket": asset["bucket"], "Key": asset["object_key"]}
        if asset.get("version_id"):
            client.delete_object(**arguments, VersionId=asset["version_id"])
            return
        # An ambiguous upload may have created an unknown version. List only its
        # generated key and delete exact matches; never delete an entire prefix.
        paginator = client.get_paginator("list_object_versions")
        found = False
        try:
            for page in paginator.paginate(
                Bucket=asset["bucket"], Prefix=asset["object_key"]
            ):
                for row in page.get("Versions", []) + page.get("DeleteMarkers", []):
                    if row["Key"] == asset["object_key"]:
                        client.delete_object(**arguments, VersionId=row["VersionId"])
                        found = True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {
                "NoSuchKey",
                "NoSuchBucket",
            }:
                raise
        if not found:
            client.delete_object(**arguments)


async def cleanup_once(limit=20):
    db, completed = get_db(), 0
    for _ in range(limit):
        now, token = utcnow(), uuid4().hex
        job = await db["media_cleanup_jobs"].find_one_and_update(
            {
                "$or": [
                    {"state": "pending", "run_after": {"$lte": now}},
                    {"state": "processing", "lease_until": {"$lte": now}},
                ]
            },
            {
                "$set": {
                    "state": "processing",
                    "lease_until": now + timedelta(seconds=120),
                    "claim_token": token,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if not job:
            break
        claim = {"_id": job["_id"], "claim_token": token, "state": "processing"}

        async def prepare(session):
            if not await db["media_cleanup_jobs"].find_one(claim, session=session):
                return None
            asset = await db["media_assets"].find_one(
                {"_id": oid(job["asset_id"])}, session=session
            )
            if not asset or asset["state"] == "deleted":
                await db["media_cleanup_jobs"].update_one(
                    claim,
                    {"$set": {"state": "completed", "finished_at": utcnow()}},
                    session=session,
                )
                return None
            if await has_references(job["asset_id"], session):
                await db["media_cleanup_jobs"].update_one(
                    claim,
                    {
                        "$set": {
                            "state": "pending",
                            "run_after": utcnow()
                            + timedelta(seconds=settings.CONTENT_MEDIA_GRACE_SECONDS),
                        }
                    },
                    session=session,
                )
                return None
            # Attachments also write this document, preventing attach/delete races.
            await db["media_assets"].update_one(
                {"_id": asset["_id"]}, {"$set": {"state": "deleting"}}, session=session
            )
            return asset

        try:
            asset = await run_transaction(prepare)
            if asset is None:
                continue
            await run_in_threadpool(delete_blob, asset)

            async def finish(session):
                if not await db["media_cleanup_jobs"].find_one(claim, session=session):
                    return
                await db["media_assets"].update_one(
                    {"_id": asset["_id"], "state": "deleting"},
                    {"$set": {"state": "deleted", "deleted_at": utcnow()}},
                    session=session,
                )
                await db["media_cleanup_jobs"].update_one(
                    claim,
                    {"$set": {"state": "completed", "finished_at": utcnow()}},
                    session=session,
                )
                await audit(
                    "media.delete", "media_assets", asset["_id"], session=session
                )

            await run_transaction(finish)
            completed += 1
        except Exception as exc:
            attempts = job.get("attempts", 0) + 1
            await db["media_cleanup_jobs"].update_one(
                claim,
                {
                    "$set": {
                        "attempts": attempts,
                        "state": "failed" if attempts >= 10 else "pending",
                        "run_after": utcnow()
                        + timedelta(seconds=min(3600, 2**attempts * 10)),
                        "last_error": type(exc).__name__,
                    }
                },
            )
            logger.warning("Media cleanup will retry (%s)", type(exc).__name__)
    return completed


async def cleanup_loop():
    while True:
        try:
            await cleanup_once()
        except Exception as exc:
            logger.warning("Media cleanup unavailable (%s)", type(exc).__name__)
        await asyncio.sleep(settings.CONTENT_CLEANUP_INTERVAL_SECONDS)


class UploadBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not path.endswith(("/media/images", "/media/audio"))
        ):
            return await self.app(scope, receive, send)
        maximum = (
            settings.MAX_AUDIO_SIZE_BYTES
            if path.endswith("/media/audio")
            else MAX_IMAGE_SIZE_BYTES
        ) + 65536
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = maximum + 1
        if length > maximum:
            from starlette.responses import JSONResponse

            return await JSONResponse(
                {"detail": "Upload body exceeds the configured size limit"},
                status_code=413,
            )(scope, receive, send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > maximum:
                raise HTTPException(
                    413, "Upload body exceeds the configured size limit"
                )
            return message

        await self.app(scope, limited_receive, send)
