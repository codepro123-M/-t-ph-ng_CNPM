import heapq
import logging
import math

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import PyMongoError

from app.content.common import (
    hydrate,
    next_version,
    oid,
    public_menu,
    record_change,
    snapshot_for,
)
from app.content.media import queue_cleanup, touch_assets
from app.core.audit import audit, public_document, read_snapshot, run_transaction
from app.core.config import settings
from app.core.database import get_db
from app.core.security import utcnow

logger = logging.getLogger("smartstay.content")
TEXT_FIELDS = {"name", "description", "check_in_instructions"}


async def verified_owner(user_id, session):
    row = await get_db()["admin_users"].find_one(
        {
            "_id": oid(user_id),
            "is_active": True,
            "is_verified": True,
            "is_poi_owner_verified": True,
        },
        session=session,
    )
    if not row:
        raise HTTPException(409, "Owner is inactive or no longer verified")
    # Serialize content writes against account deactivation/verification changes.
    await get_db()["admin_users"].update_one(
        {"_id": row["_id"], "auth_version": row["auth_version"]},
        {"$inc": {"content_write_revision": 1}},
        session=session,
    )
    return row


async def get_poi(poi_id, session=None, *, owner_id=None, public=False):
    query = {"_id": oid(poi_id)}
    if owner_id is not None:
        query["owner_id"] = owner_id
    if public:
        query["is_active"] = True
    poi = await get_db()["pois"].find_one(query, session=session)
    if not poi:
        raise HTTPException(404, "POI not found")
    return poi


def source_fields(payload):
    data = payload.model_dump(
        mode="json", exclude={"owner_id", "is_active", "expected_revision"}
    )
    data["location"] = {
        "type": "Point",
        "coordinates": [data["longitude"], data["latitude"]],
    }
    data["source_language"] = "vi"
    return data


async def notify(owner_id, kind, poi_id, submission_id, note, session):
    await get_db()["owner_notifications"].insert_one(
        {
            "owner_id": owner_id,
            "kind": kind,
            "poi_id": poi_id,
            "submission_id": submission_id,
            "admin_note": note,
            "is_read": False,
            "created_at": utcnow(),
        },
        session=session,
    )


async def insert_poi(
    payload, owner_id, is_active, actor, session, *, owner_media=False, admin_note=""
):
    if owner_id:
        await verified_owner(owner_id, session)
    await touch_assets(
        payload.images,
        session,
        owner_id=owner_id if owner_media else None,
        publish=is_active,
    )
    version, stamp = await next_version(session)
    poi = source_fields(payload) | {
        "_id": ObjectId(),
        "owner_id": owner_id,
        "is_active": is_active,
        "revision": 1,
        "source_revision": 1,
        "created_at": stamp,
        "updated_at": stamp,
        "admin_note": admin_note,
    }
    await get_db()["pois"].insert_one(poi, session=session)
    await record_change(poi, version, stamp, session)
    await audit("poi.create", "pois", poi["_id"], actor, session=session)
    return poi


async def replace_poi(
    poi,
    payload,
    actor,
    session,
    *,
    expected_revision,
    owner_media=False,
    owner_id=None,
    is_active=None,
    admin_note="",
):
    if poi["revision"] != expected_revision:
        raise HTTPException(
            409, "POI changed since this edit was prepared; reload before resubmitting"
        )
    new_owner = owner_id
    if new_owner:
        await verified_owner(new_owner, session)
    active = poi["is_active"] if is_active is None else is_active
    data = source_fields(payload)
    await touch_assets(
        payload.images,
        session,
        owner_id=poi["owner_id"] if owner_media else None,
        existing=poi["images"],
        publish=active,
    )
    await queue_cleanup(set(poi["images"]) - set(payload.images), session)
    changed_text = any(poi[field] != data[field] for field in TEXT_FIELDS)
    if changed_text:
        if poi.get("audio_asset_id"):
            await queue_cleanup(
                [poi["audio_asset_id"]], session, reason="source_text_changed"
            )
        old = (
            await get_db()["poi_localizations"]
            .find({"poi_id": str(poi["_id"])}, session=session)
            .to_list(length=64)
        )
        await queue_cleanup(
            [row["audio_asset_id"] for row in old if row.get("audio_asset_id")], session
        )
        await get_db()["poi_localizations"].delete_many(
            {"poi_id": str(poi["_id"])}, session=session
        )
    elif active and not poi["is_active"]:
        translations = (
            await get_db()["poi_localizations"]
            .find({"poi_id": str(poi["_id"])}, session=session)
            .to_list(length=64)
        )
        await touch_assets(
            [
                row["audio_asset_id"]
                for row in translations
                if row.get("audio_asset_id")
            ],
            session,
            kind="audio",
            publish=True,
        )
        if poi.get("audio_asset_id"):
            await touch_assets(
                [poi["audio_asset_id"]], session, kind="audio", publish=True
            )
    version, stamp = await next_version(session)
    changes = data | {
        "owner_id": new_owner,
        "is_active": active,
        "revision": poi["revision"] + 1,
        "source_revision": poi["source_revision"] + int(changed_text),
        "updated_at": stamp,
        "admin_note": admin_note,
        "audio_asset_id": None if changed_text else poi.get("audio_asset_id"),
    }
    result = await get_db()["pois"].update_one(
        {"_id": poi["_id"], "revision": expected_revision},
        {"$set": changes},
        session=session,
    )
    if not result.modified_count:
        raise HTTPException(409, "POI changed concurrently; reload")
    updated = poi | changes
    await record_change(updated, version, stamp, session)
    await audit(
        "poi.update",
        "pois",
        poi["_id"],
        actor,
        session=session,
        details={"fields": sorted(payload.model_fields_set)},
    )
    return updated


async def create_poi(payload, actor):
    async def operation(session):
        return public_document(
            await insert_poi(
                payload, payload.owner_id, payload.is_active, actor, session
            )
        )

    return await run_transaction(operation)


async def update_poi(poi_id, payload, actor):
    from pydantic import ValidationError
    from app.content.schemas import POIData

    async def operation(session):
        poi = await get_poi(poi_id, session)
        changes = payload.model_dump(
            mode="json", exclude_unset=True, exclude={"expected_revision"}
        )
        if not changes:
            raise HTTPException(422, "No fields to update")
        owner_id = changes.pop("owner_id", poi.get("owner_id"))
        active = changes.pop("is_active", poi["is_active"])
        if active is None:
            raise HTTPException(422, "is_active cannot be null")
        try:
            merged = POIData.model_validate(
                {key: poi[key] for key in POIData.model_fields} | changes
            )
        except ValidationError:
            raise HTTPException(422, "Invalid POI fields") from None
        return public_document(
            await replace_poi(
                poi,
                merged,
                actor,
                session,
                expected_revision=payload.expected_revision,
                owner_id=owner_id,
                is_active=active,
                admin_note=poi.get("admin_note", ""),
            )
        )

    return await run_transaction(operation)


async def submit(payload, actor):
    async def operation(session):
        await verified_owner(actor["sub"], session)
        existing = []
        if payload.kind == "update":
            poi = await get_poi(payload.poi_id, session, owner_id=actor["sub"])
            if poi["revision"] != payload.expected_revision:
                raise HTTPException(409, "POI changed; reload before submitting")
            # Touch the POI so transfer/deletion cannot race this submission.
            await get_db()["pois"].update_one(
                {"_id": poi["_id"]},
                {"$inc": {"submission_revision": 1}},
                session=session,
            )
            existing = poi["images"]
        await touch_assets(
            payload.payload.images, session, owner_id=actor["sub"], existing=existing
        )
        row = payload.model_dump(mode="json") | {
            "owner_id": actor["sub"],
            "status": "pending",
            "created_at": utcnow(),
            "admin_note": "",
        }
        result = await get_db()["poi_submissions"].insert_one(row, session=session)
        await audit(
            "submission.create",
            "poi_submissions",
            result.inserted_id,
            actor,
            session=session,
        )
        return public_document(row)

    return await run_transaction(operation)


async def review(submission_id, payload, actor):
    from app.content.schemas import POIData

    async def operation(session):
        db = get_db()
        row = await db["poi_submissions"].find_one(
            {"_id": oid(submission_id)}, session=session
        )
        if not row:
            raise HTTPException(404, "Submission not found")
        if row["status"] != "pending":
            raise HTTPException(409, "Submission has already been reviewed")
        if row["owner_id"] == actor["sub"] and actor["realm"] == "admin_users":
            raise HTTPException(403, "You cannot review your own submission")
        poi_id = row.get("poi_id")
        if payload.status == "approved":
            needed = "poi.create" if row["kind"] == "create" else "poi.update"
            if needed not in actor["permissions"]:
                raise HTTPException(403, "Permission required: " + needed)
            await verified_owner(row["owner_id"], session)
            source = POIData.model_validate(row["payload"])
            if row["kind"] == "create":
                poi = await insert_poi(
                    source,
                    row["owner_id"],
                    True,
                    actor,
                    session,
                    owner_media=True,
                    admin_note=payload.admin_note,
                )
            else:
                poi = await get_poi(poi_id, session, owner_id=row["owner_id"])
                poi = await replace_poi(
                    poi,
                    source,
                    actor,
                    session,
                    expected_revision=row["expected_revision"],
                    owner_media=True,
                    owner_id=row["owner_id"],
                    admin_note=payload.admin_note,
                )
            poi_id = str(poi["_id"])
        else:
            await queue_cleanup(
                row["payload"]["images"], session, reason="submission_rejected"
            )
        changes = {
            "status": payload.status,
            "admin_note": payload.admin_note,
            "reviewed_at": utcnow(),
            "reviewed_by": actor["sub"],
            "poi_id": poi_id,
        }
        result = await db["poi_submissions"].update_one(
            {"_id": row["_id"], "status": "pending"}, {"$set": changes}, session=session
        )
        if not result.modified_count:
            raise HTTPException(409, "Submission changed concurrently")
        await notify(
            row["owner_id"],
            "submission." + payload.status,
            poi_id,
            submission_id,
            payload.admin_note,
            session,
        )
        await audit(
            "submission." + payload.status,
            "poi_submissions",
            submission_id,
            actor,
            session=session,
            details={"status": payload.status},
        )
        return public_document(row | changes)

    return await run_transaction(operation)


async def delete_poi(poi_id, actor):
    async def operation(session):
        db = get_db()
        poi = await get_poi(poi_id, session)
        localizations = (
            await db["poi_localizations"]
            .find({"poi_id": poi_id}, session=session)
            .to_list(length=64)
        )
        pending = (
            await db["poi_submissions"]
            .find({"poi_id": poi_id, "status": "pending"}, session=session)
            .to_list(length=None)
        )
        assets = (
            list(poi["images"])
            + ([poi["audio_asset_id"]] if poi.get("audio_asset_id") else [])
            + [
                row["audio_asset_id"]
                for row in localizations
                if row.get("audio_asset_id")
            ]
        )
        for row in pending:
            assets.extend(row["payload"]["images"])
        await queue_cleanup(assets, session, reason="poi_deleted")
        await db["menu_items"].delete_many({"poi_id": poi_id}, session=session)
        await db["poi_localizations"].delete_many({"poi_id": poi_id}, session=session)
        await db["poi_submissions"].update_many(
            {"poi_id": poi_id, "status": "pending"},
            {
                "$set": {
                    "status": "cancelled",
                    "admin_note": "POI deleted",
                    "reviewed_at": utcnow(),
                    "reviewed_by": actor["sub"],
                }
            },
            session=session,
        )
        await db["pois"].delete_one({"_id": poi["_id"]}, session=session)
        version, stamp = await next_version(session)
        await record_change(poi, version, stamp, session, removed=True)
        if poi.get("owner_id"):
            await notify(
                poi["owner_id"], "poi.deleted", poi_id, None, "POI deleted", session
            )
        await audit(
            "poi.delete",
            "pois",
            poi_id,
            actor,
            session=session,
            details={"count": len(localizations)},
        )

    await run_transaction(operation)


async def menu_mutation(
    poi_id, actor, *, payload=None, item_id=None, deleting=False, owner=False
):
    async def operation(session):
        db = get_db()
        if owner:
            await verified_owner(actor["sub"], session)
        poi = await get_poi(poi_id, session, owner_id=actor["sub"] if owner else None)
        old = None
        if item_id:
            old = await db["menu_items"].find_one(
                {"_id": oid(item_id), "poi_id": poi_id}, session=session
            )
            if not old:
                raise HTTPException(404, "Menu item not found")
            if not deleting and old["revision"] != payload.expected_revision:
                raise HTTPException(409, "Menu item changed; reload")
        elif (
            await db["menu_items"].count_documents({"poi_id": poi_id}, session=session)
            >= 200
        ):
            raise HTTPException(409, "A POI can contain at most 200 menu items")
        version, stamp = await next_version(session)
        if deleting:
            await db["menu_items"].delete_one({"_id": old["_id"]}, session=session)
            result, action, resource_id = None, "menu.delete", item_id
        else:
            data = payload.model_dump(
                mode="json", exclude={"poi_id", "expected_revision"}
            ) | {"poi_id": poi_id, "updated_at": stamp}
            if old:
                data["revision"] = old["revision"] + 1
                await db["menu_items"].update_one(
                    {"_id": old["_id"], "revision": old["revision"]},
                    {"$set": data},
                    session=session,
                )
                row, action = old | data, "menu.update"
            else:
                row, action = (
                    data | {"_id": ObjectId(), "revision": 1, "created_at": stamp},
                    "menu.create",
                )
                await db["menu_items"].insert_one(row, session=session)
            result, resource_id = public_menu(row), str(row["_id"])
        changes = {"revision": poi["revision"] + 1, "updated_at": stamp}
        await db["pois"].update_one(
            {"_id": poi["_id"]}, {"$set": changes}, session=session
        )
        await record_change(poi | changes, version, stamp, session)
        await audit(action, "menu_items", resource_id, actor, session=session)
        return result

    return await run_transaction(operation)


async def set_localization(poi_id, language, payload, actor, *, deleting=False):
    async def operation(session):
        db = get_db()
        poi = await get_poi(poi_id, session)
        query = {"poi_id": poi_id, "language": language}
        old = await db["poi_localizations"].find_one(query, session=session)
        if deleting:
            if not old:
                raise HTTPException(404, "Localization not found")
            await db["poi_localizations"].delete_one(query, session=session)
            new_audio = None
        else:
            if payload.source_revision != poi["source_revision"]:
                raise HTTPException(
                    409, "Source text changed; translate the current revision"
                )
            if (
                not old
                and await db["poi_localizations"].count_documents(
                    {"poi_id": poi_id}, session=session
                )
                >= 64
            ):
                raise HTTPException(409, "A POI can contain at most 64 translations")
            new_audio = payload.audio_asset_id
            if new_audio:
                await touch_assets(
                    [new_audio], session, kind="audio", publish=poi["is_active"]
                )
            await db["poi_localizations"].update_one(
                query,
                {
                    "$set": payload.model_dump(mode="json")
                    | query
                    | {"updated_at": utcnow()}
                },
                upsert=True,
                session=session,
            )
        if old and old.get("audio_asset_id") and old["audio_asset_id"] != new_audio:
            await queue_cleanup(
                [old["audio_asset_id"]], session, reason="audio_replaced"
            )
        version, stamp = await next_version(session)
        changes = {"revision": poi["revision"] + 1, "updated_at": stamp}
        await db["pois"].update_one(
            {"_id": poi["_id"]}, {"$set": changes}, session=session
        )
        await record_change(poi | changes, version, stamp, session)
        await audit(
            "localization.delete" if deleting else "localization.update",
            "poi_localizations",
            poi_id + ":" + language,
            actor,
            session=session,
        )
        return {"poi_id": poi_id, "language": language, "revision": changes["revision"]}

    return await run_transaction(operation)


def haversine(lat1, lon1, lat2, lon2):
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    delta_lat, delta_lon = lat2 - lat1, math.radians(lon2 - lon1)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, max(0, value))))


async def nearby(latitude, longitude, radius_m, language, limit, category=None):
    db = get_db()
    query = {"is_active": True} | ({"category": category} if category else {})
    async with read_snapshot() as session:
        pipeline = [
            {
                "$geoNear": {
                    "near": {"type": "Point", "coordinates": [longitude, latitude]},
                    "key": "location",
                    "distanceField": "distance_m",
                    "maxDistance": radius_m,
                    "spherical": True,
                    "query": query,
                }
            },
            {"$sort": {"distance_m": 1, "_id": 1}},
            {"$limit": limit},
        ]
        engine = "geoNear"
        try:
            pois = (
                await db["pois"]
                .aggregate(
                    pipeline,
                    session=session,
                    maxTimeMS=settings.CONTENT_QUERY_TIMEOUT_MS,
                )
                .to_list(length=limit)
            )
        except PyMongoError as exc:
            logger.warning(
                "Geospatial query fell back to Haversine (%s)", type(exc).__name__
            )
            engine, heap = "haversine", []
            async for row in db["pois"].find(
                query, session=session, max_time_ms=settings.CONTENT_QUERY_TIMEOUT_MS
            ):
                distance = haversine(
                    latitude, longitude, row["latitude"], row["longitude"]
                )
                if distance <= radius_m:
                    # Keep only the nearest N candidates while scanning all POIs.
                    key = (-distance, -int(str(row["_id"]), 16))
                    entry = (key, row | {"distance_m": distance})
                    if len(heap) < limit:
                        heapq.heappush(heap, entry)
                    elif key > heap[0][0]:
                        heapq.heapreplace(heap, entry)
            pois = [entry[1] for entry in heap]
            pois.sort(key=lambda row: (row["distance_m"], str(row["_id"])))
        items = []
        for poi in pois:
            item = hydrate(await snapshot_for(poi, session), language)
            item["distance_m"] = round(poi["distance_m"], 3)
            item["within_trigger_radius"] = poi["distance_m"] <= poi["geofence_radius"]
            items.append(item)
        return {
            "items": items,
            "query_engine": engine,
            "radius_m": radius_m,
            "language": language,
            "requested_lang": language,
            "spatial_engine": "mongo_geonear"
            if engine == "geoNear"
            else "haversine_fallback",
            "total": len(items),
            "center": {"lat": latitude, "lng": longitude, "radius_m": radius_m},
        }
