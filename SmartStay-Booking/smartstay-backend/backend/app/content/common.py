from datetime import timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from app.core.database import get_db
from app.core.security import utcnow


def oid(value):
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "Resource not found")
    return ObjectId(value)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


async def next_version(session):
    collection = get_db()["content_dataset_versions"]
    previous = await collection.find_one({"_id": "poi"}, session=session)
    now = utcnow()
    stamp = max(now, aware(previous["updated_at"]) + timedelta(milliseconds=1))
    stamp = stamp.replace(microsecond=(stamp.microsecond // 1000) * 1000)
    row = await collection.find_one_and_update(
        {"_id": "poi", "version": previous["version"]},
        {"$inc": {"version": 1}, "$set": {"updated_at": stamp}},
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    if not row:
        raise HTTPException(409, "Dataset changed concurrently; retry")
    return row["version"], stamp


async def snapshot_for(poi, session):
    poi_id = str(poi["_id"])
    menus = (
        await get_db()["menu_items"]
        .find({"poi_id": poi_id}, session=session)
        .sort("_id", 1)
        .to_list(length=201)
    )
    localizations = (
        await get_db()["poi_localizations"]
        .find({"poi_id": poi_id}, session=session)
        .to_list(length=65)
    )
    if len(menus) > 200 or len(localizations) > 64:
        raise HTTPException(409, "POI content exceeds the supported limits")
    return {"poi": poi, "menu_items": menus, "localizations": localizations}


async def record_change(poi, version, stamp, session, *, removed=False):
    removed = removed or not poi.get("is_active", True)
    await get_db()["content_changes"].insert_one(
        {
            "_id": version,
            "version": version,
            "poi_id": str(poi["_id"]),
            "operation": "remove" if removed else "upsert",
            "changed_at": stamp,
            "snapshot": None if removed else await snapshot_for(poi, session),
        },
        session=session,
    )


def hydrate(snapshot, requested_language):
    source = snapshot["poi"]
    translations = {
        row["language"]: row
        for row in snapshot["localizations"]
        if row.get("source_revision") == source["source_revision"]
    }
    if requested_language == "vi":
        text, language, tier = source, "vi", 1
    elif requested_language in translations:
        text, language, tier = translations[requested_language], requested_language, 1
    elif "en" in translations:
        text, language, tier = translations["en"], "en", 2
    else:
        text, language, tier = source, "vi", 3
    audio_id = text.get("audio_asset_id") if tier != 3 else None
    return {
        "id": str(source["_id"]),
        "name": text["name"],
        "description": text["description"],
        "check_in_instructions": text["check_in_instructions"],
        "source_language": "vi",
        "requested_language": requested_language,
        "language": language,
        "resolved_lang": language,
        "fallback_tier": tier,
        "audio_url": f"/media/{audio_id}" if audio_id else None,
        "category": source["category"],
        "address": source["address"],
        "latitude": source["latitude"],
        "longitude": source["longitude"],
        "lat": source["latitude"],
        "lng": source["longitude"],
        "location": source["location"],
        "images": [f"/media/{asset_id}" for asset_id in source["images"]],
        "geofence_radius": source["geofence_radius"],
        "trigger_radius": source["geofence_radius"],
        "audio_priority": source["audio_priority"],
        "revision": source["revision"],
        "source_revision": source["source_revision"],
        "updated_at": aware(source["updated_at"]),
        "menu_items": [
            public_menu(row)
            for row in snapshot["menu_items"]
            if row.get("is_available", True)
        ],
    }


def public_menu(row):
    return {
        "id": str(row["_id"]),
        "poi_id": row["poi_id"],
        "name": row["name"],
        "description": row["description"],
        "kind": row["kind"],
        "price": row["price"],
        "currency": row["currency"],
        "capacity": row["capacity"],
        "inventory": row.get("inventory", 1),
        "amenities": row["amenities"],
        "is_available": row["is_available"],
        "language": "vi",
        "revision": row["revision"],
    }
