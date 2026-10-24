"""Versioned immutable snapshots keep full/delta pagination stable during writes."""

import hashlib
import hmac
import json
from datetime import timedelta

import jwt
from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.encoders import jsonable_encoder

from app.content.common import aware, hydrate
from app.content.schemas import language_code
from app.core.audit import read_snapshot
from app.core.config import settings
from app.core.database import get_db
from app.core.security import utcnow


def cursor_key():
    return hmac.new(
        settings.JWT_SECRET.encode(), b"smartstay-content-sync-v1", hashlib.sha256
    ).digest()


def encode_cursor(payload, *, page=False):
    claims = payload | {
        "type": "content_sync",
        "iss": settings.JWT_ISSUER,
        "aud": "smartstay-content-sync",
        "iat": utcnow(),
    }
    if page:
        claims.setdefault("exp", utcnow() + timedelta(seconds=3600))
    return jwt.encode(claims, cursor_key(), algorithm="HS256")


def decode_cursor(token):
    try:
        if len(token) > 4096:
            raise ValueError("oversized")
        claims = jwt.decode(
            token,
            cursor_key(),
            algorithms=["HS256"],
            issuer=settings.JWT_ISSUER,
            audience="smartstay-content-sync",
            options={
                "require": ["type", "kind", "since", "language", "dataset_id", "iat"]
            },
        )
        if claims["type"] != "content_sync" or claims["kind"] not in {
            "page",
            "checkpoint",
        }:
            raise ValueError("type")
        if type(claims["since"]) is not int or claims["since"] < 0:
            raise ValueError("version")
        language_code(claims["language"])
        if claims["kind"] == "page":
            if (
                type(claims.get("until")) is not int
                or claims["until"] < claims["since"]
            ):
                raise ValueError("range")
            if claims.get("mode") not in {"full", "delta"} or not isinstance(
                claims.get("after"), str
            ):
                raise ValueError("page")
            if (
                type(claims.get("page_size")) is not int
                or not 1 <= claims["page_size"] <= 500
                or "exp" not in claims
            ):
                raise ValueError("limit")
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(
            400, "Invalid or expired sync cursor; restart a full sync"
        ) from None


def etag_matches(header, etag):
    if not header:
        return False
    return any(
        value.strip() == "*"
        or value.strip().removeprefix("W/") == etag.removeprefix("W/")
        for value in header.split(",")
    )


async def load_all(
    *, cursor=None, updated_after=None, language=None, limit=None, if_none_match=None
):
    db = get_db()
    claims = decode_cursor(cursor) if cursor else None
    if claims and updated_after is not None:
        raise HTTPException(400, "Use either cursor or updated_after")
    try:
        language = language_code(language or (claims["language"] if claims else "vi"))
    except ValueError:
        raise HTTPException(422, "Invalid language code") from None
    if claims and claims["language"] != language:
        raise HTTPException(400, "Language changed; restart a full sync")
    if (
        claims
        and claims["kind"] == "page"
        and limit is not None
        and limit != claims["page_size"]
    ):
        raise HTTPException(400, "Keep the same page size while continuing a sync")
    limit = limit or (
        claims["page_size"] if claims and claims["kind"] == "page" else 200
    )
    async with read_snapshot() as session:
        dataset = await db["content_dataset_versions"].find_one(
            {"_id": "poi"}, session=session
        )
        current = dataset["version"]
        if claims and (
            claims["dataset_id"] != dataset["dataset_id"]
            or claims["since"] > current
            or claims.get("until", 0) > current
        ):
            raise HTTPException(409, "Dataset was reset; restart a full sync")
        since, upper, after, mode = 0, current, "", "full"
        if claims:
            since, mode = claims["since"], "delta"
            if claims["kind"] == "page":
                upper, after, mode = claims["until"], claims["after"], claims["mode"]
        elif updated_after is not None:
            if updated_after.tzinfo is None:
                raise HTTPException(422, "updated_after must include a timezone")
            stamp = aware(updated_after)
            previous = (
                await db["content_changes"]
                .find(
                    {"changed_at": {"$lte": stamp}, "version": {"$lte": upper}},
                    session=session,
                )
                .sort("version", -1)
                .limit(1)
                .to_list(length=1)
            )
            since, mode = (previous[0]["version"] if previous else 0), "delta"
        latest = (
            await db["content_changes"].find_one({"_id": upper}, session=session)
            if upper
            else None
        )
        as_of = aware(latest["changed_at"] if latest else dataset["created_at"])
        identity = json.dumps(
            [
                dataset["dataset_id"],
                upper,
                since,
                after,
                mode,
                language,
                limit,
                "content-v1",
            ],
            separators=(",", ":"),
        )
        etag = 'W/"poi-' + hashlib.sha256(identity.encode()).hexdigest()[:32] + '"'
        headers = {
            "ETag": etag,
            "Cache-Control": "no-cache",
            "Content-Language": language,
        }
        # A continuation must always return the next page, even with a cached ETag.
        if not (claims and claims["kind"] == "page") and etag_matches(
            if_none_match, etag
        ):
            return Response(status_code=304, headers=headers)
        pipeline = [
            {"$match": {"version": {"$gt": since, "$lte": upper}}},
            {"$sort": {"poi_id": 1, "version": -1}},
            {"$group": {"_id": "$poi_id", "change": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$change"}},
            {
                "$match": {"poi_id": {"$gt": after}}
                | ({"operation": "upsert"} if mode == "full" else {})
            },
            {"$sort": {"poi_id": 1}},
            {"$limit": limit + 1},
        ]
        rows = (
            await db["content_changes"]
            .aggregate(
                pipeline, session=session, maxTimeMS=settings.CONTENT_QUERY_TIMEOUT_MS
            )
            .to_list(length=limit + 1)
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        context = {"dataset_id": dataset["dataset_id"], "language": language}
        if has_more:
            if claims and claims["kind"] == "page":
                context["exp"] = claims["exp"]
            next_cursor = encode_cursor(
                context
                | {
                    "kind": "page",
                    "since": since,
                    "until": upper,
                    "after": rows[-1]["poi_id"],
                    "mode": mode,
                    "page_size": limit,
                },
                page=True,
            )
        else:
            next_cursor = encode_cursor(
                context | {"kind": "checkpoint", "since": upper}
            )
        return JSONResponse(
            jsonable_encoder(
                {
                    "items": [
                        hydrate(row["snapshot"], language)
                        for row in rows
                        if row["operation"] == "upsert"
                    ],
                    "removed_poi_ids": [
                        row["poi_id"] for row in rows if row["operation"] == "remove"
                    ],
                    "sync_cursor": next_cursor,
                    "has_more": has_more,
                    "mode": mode,
                    "is_delta": mode == "delta",
                    "requested_lang": language,
                    "total": sum(row["operation"] == "upsert" for row in rows),
                    "etag": etag,
                    "dataset_version": upper,
                    "as_of": as_of,
                }
            ),
            headers=headers,
        )
