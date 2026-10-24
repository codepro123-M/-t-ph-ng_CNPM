import hashlib
import json
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.bookings.schemas import business_today
from app.core.audit import audit, read_snapshot, run_transaction
from app.core.database import get_db
from app.core.security import utcnow

ACTIVE_STATUSES = ("pending", "confirmed")


def oid(value):
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "Booking not found")
    return ObjectId(value)


def nights(start, end):
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days)]


def present(row):
    # Deliberately omit internal request hashes and inventory locks.
    keys = (
        "code",
        "poi_id",
        "room_type_id",
        "property_name",
        "property_address",
        "room_name",
        "contact_name",
        "email",
        "phone",
        "notes",
        "check_in",
        "check_out",
        "guests",
        "nights",
        "unit_price",
        "total_price",
        "currency",
        "status",
        "revision",
        "created_at",
        "updated_at",
    )
    return {"id": str(row["_id"])} | {key: row[key] for key in keys}


async def room_for(payload, session=None):
    db = get_db()
    poi = await db["pois"].find_one(
        {"_id": oid(payload.poi_id), "is_active": True}, session=session
    )
    room = await db["menu_items"].find_one(
        {
            "_id": oid(payload.room_type_id),
            "poi_id": payload.poi_id,
            "kind": "room_type",
            "is_available": True,
        },
        session=session,
    )
    if not poi or not room:
        raise HTTPException(404, "Published property or room type not found")
    if payload.guests > room.get("capacity", 2):
        raise HTTPException(409, "Guest count exceeds the room capacity")
    try:
        price = Decimal(str(room["price"]))
        if not price.is_finite() or price < 0:
            raise ValueError()
    except (KeyError, InvalidOperation, ValueError):
        raise HTTPException(409, "Room price is unavailable") from None
    inventory = room.get("inventory", 1)
    if not isinstance(inventory, int) or inventory < 1:
        raise HTTPException(409, "Room inventory is unavailable")
    return poi, room, price, inventory


async def availability(payload):
    async with read_snapshot() as session:
        _, room, price, inventory = await room_for(payload, session)
        dates = nights(payload.check_in, payload.check_out)
        rows = (
            await get_db()["booking_inventory"]
            .find(
                {"_id": {"$in": [payload.room_type_id + ":" + day for day in dates]}},
                session=session,
            )
            .to_list(length=30)
        )
    remaining = max(0, inventory - max((row["reserved"] for row in rows), default=0))
    return {
        "available": remaining > 0,
        "remaining": remaining,
        "nights": len(dates),
        "unit_price": str(price),
        "total_price": str(price * len(dates)),
        "currency": room["currency"],
    }


def fingerprint(payload):
    data = payload.model_dump(mode="json", exclude={"request_id"})
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def same_request(row, request_hash):
    if row["request_hash"] != request_hash:
        raise HTTPException(409, "Request ID was already used for a different booking")
    return present(row)


async def create_booking(payload, actor):
    db = get_db()
    key = {"customer_id": actor["sub"], "request_id": str(payload.request_id)}
    request_hash, booking_id = fingerprint(payload), ObjectId()

    async def operation(session):
        old = await db["bookings"].find_one(key, session=session)
        if old:
            return same_request(old, request_hash)
        poi, room, price, inventory = await room_for(payload, session)
        # Serialize bookings with room edits and property unpublishing too.
        await db["pois"].update_one(
            {"_id": poi["_id"]}, {"$inc": {"booking_revision": 1}}, session=session
        )
        await db["menu_items"].update_one(
            {"_id": room["_id"]}, {"$inc": {"booking_revision": 1}}, session=session
        )
        dates = nights(payload.check_in, payload.check_out)
        for day in dates:
            identity = payload.room_type_id + ":" + day
            await db["booking_inventory"].update_one(
                {"_id": identity},
                {
                    "$setOnInsert": {
                        "room_type_id": payload.room_type_id,
                        "night": day,
                        "reserved": 0,
                    }
                },
                upsert=True,
                session=session,
            )
            slot = await db["booking_inventory"].find_one_and_update(
                {"_id": identity, "reserved": {"$lt": inventory}},
                {"$inc": {"reserved": 1}},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if slot is None:
                raise HTTPException(
                    409, "Room is fully booked for one or more selected nights"
                )
        stamp = utcnow()
        row = {
            "_id": booking_id,
            "code": "SS-" + secrets.token_hex(6).upper(),
            **key,
            "request_hash": request_hash,
            "poi_id": payload.poi_id,
            "room_type_id": payload.room_type_id,
            "property_name": poi["name"],
            "property_address": poi["address"],
            "room_name": room["name"],
            "contact_name": payload.contact_name,
            "email": payload.email,
            "phone": payload.phone,
            "notes": payload.notes,
            "check_in": payload.check_in.isoformat(),
            "check_out": payload.check_out.isoformat(),
            "guests": payload.guests,
            "nights": len(dates),
            "unit_price": str(price),
            "total_price": str(price * len(dates)),
            "currency": room["currency"],
            "status": "pending",
            "revision": 1,
            "created_at": stamp,
            "updated_at": stamp,
        }
        await db["bookings"].insert_one(row, session=session)
        await audit(
            "booking.create",
            "bookings",
            booking_id,
            actor,
            session=session,
            details={"status": "pending"},
        )
        return present(row)

    try:
        return await run_transaction(operation)
    except DuplicateKeyError:
        old = await db["bookings"].find_one(key)
        if old:
            return same_request(old, request_hash)
        raise HTTPException(
            409, "Concurrent reservation; retry with the same request ID"
        ) from None


async def update_booking(booking_id, payload, actor, *, customer=False):
    db = get_db()
    query = {"_id": oid(booking_id)}
    if customer:
        query["customer_id"] = actor["sub"]
    target = "cancelled" if customer else payload.status

    async def operation(session):
        row = await db["bookings"].find_one(query, session=session)
        if not row:
            raise HTTPException(404, "Booking not found")
        if row["revision"] != payload.expected_revision:
            raise HTTPException(409, "Booking changed; reload and retry")
        allowed = {
            "pending": {"confirmed", "cancelled"},
            "confirmed": {"cancelled", "completed"},
        }
        if target not in allowed.get(row["status"], set()):
            raise HTTPException(409, "Invalid booking status transition")
        if customer and row["check_in"] < business_today().isoformat():
            raise HTTPException(409, "Contact the property to cancel after check-in")
        if target == "completed" and row["check_out"] > business_today().isoformat():
            raise HTTPException(409, "A stay can only be completed after check-out")
        if target in {"cancelled", "completed"}:
            from datetime import date

            for day in nights(
                date.fromisoformat(row["check_in"]),
                date.fromisoformat(row["check_out"]),
            ):
                slot = await db["booking_inventory"].update_one(
                    {"_id": row["room_type_id"] + ":" + day, "reserved": {"$gt": 0}},
                    {"$inc": {"reserved": -1}},
                    session=session,
                )
                if slot.modified_count != 1:
                    raise HTTPException(
                        409, "Inventory needs reconciliation; contact the administrator"
                    )
        changes = {
            "status": target,
            "updated_at": utcnow(),
            "revision": row["revision"] + 1,
        }
        await db["bookings"].update_one(
            {"_id": row["_id"], "revision": row["revision"]},
            {"$set": changes},
            session=session,
        )
        await audit(
            "booking." + target,
            "bookings",
            booking_id,
            actor,
            session=session,
            details={"status": target},
        )
        return present(row | changes)

    return await run_transaction(operation)


async def list_bookings(query, page, limit, *, admin=False):
    db = get_db()
    async with read_snapshot() as session:
        total = await db["bookings"].count_documents(query, session=session)
        # The limit bounds both memory use and returned personal data.
        cursor = (
            db["bookings"]
            .find(query, session=session)
            .sort([("created_at", -1), ("_id", -1)])
            .skip((page - 1) * limit)
            .limit(limit)
        )
        items = [present(row) async for row in cursor]
        result = {"items": items, "total": total, "page": page, "limit": limit}
        if admin:
            result["summary"] = {
                status: await db["bookings"].count_documents(
                    {"status": status}, session=session
                )
                for status in ("pending", "confirmed", "cancelled", "completed")
            }
            result["summary"]["total"] = sum(result["summary"].values())
        return result
