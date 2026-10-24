"""Real MongoDB race/rollback check. Creates and drops its own isolated test DB."""

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from app.bookings import service
from app.bookings.bootstrap import ensure_booking_indexes
from app.bookings.schemas import BookingCreate, CancelBooking, business_today
from app.core.config import settings
from app.core.database import db_manager


async def run():
    client = AsyncIOMotorClient(
        os.environ.get("SMARTSTAY_TEST_MONGO_URI", settings.MONGODB_URI),
        serverSelectionTimeoutMS=5000,
    )
    db_name = "smartstay_booking_test_" + uuid4().hex
    previous = db_manager.client, db_manager.db
    db_manager.client, db_manager.db = client, client[db_name]
    db = db_manager.db
    try:
        hello = await client.admin.command("hello")
        assert (
            hello.get("setName") or hello.get("msg") == "isdbgrid"
        ), "A real replica set is required"
        await ensure_booking_indexes()
        poi_id, room_id = ObjectId(), ObjectId()
        await db.pois.insert_one(
            {
                "_id": poi_id,
                "is_active": True,
                "name": "Concurrency test only",
                "address": "Test database",
            }
        )
        await db.menu_items.insert_one(
            {
                "_id": room_id,
                "poi_id": str(poi_id),
                "name": "Last available room",
                "kind": "room_type",
                "is_available": True,
                "price": "650000.00",
                "currency": "VND",
                "capacity": 2,
                "inventory": 1,
            }
        )
        actor = {"sub": str(ObjectId()), "realm": "auth_users"}
        start = business_today() + timedelta(days=10)
        data = {
            "poi_id": str(poi_id),
            "room_type_id": str(room_id),
            "check_in": start,
            "check_out": start + timedelta(days=3),
            "guests": 2,
            "contact_name": "Test Guest",
            "email": "test@example.com",
            "phone": "0900000000",
        }
        results = await asyncio.gather(
            *(
                service.create_booking(BookingCreate(**data, request_id=uuid4()), actor)
                for _ in range(12)
            ),
            return_exceptions=True,
        )
        wins = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(wins) == 1, repr([type(r).__name__ for r in results])
        assert all(
            isinstance(e, HTTPException) and e.status_code == 409 for e in failures
        ), repr(failures)
        assert await db.bookings.count_documents({}) == 1
        assert await db.booking_inventory.count_documents({"reserved": 1}) == 3
        print("PASS: 12 simultaneous requests, exactly one booking, no overselling")
        await service.update_booking(
            wins[0]["id"], CancelBooking(expected_revision=1), actor, customer=True
        )
        payload = BookingCreate(**data, request_id=uuid4())
        retries = await asyncio.gather(
            *(service.create_booking(payload, actor) for _ in range(8))
        )
        assert len({r["id"] for r in retries}) == 1
        assert await db.bookings.count_documents({"status": "pending"}) == 1
        assert await db.booking_inventory.count_documents({"reserved": 1}) == 3
        print("PASS: 8 simultaneous retries return the same durable booking")
        await service.update_booking(
            retries[0]["id"], CancelBooking(expected_revision=1), actor, customer=True
        )
        original_audit = service.audit

        async def failed_audit(*args, **kwargs):
            raise RuntimeError("Intentional integration audit failure")

        service.audit = failed_audit
        try:
            try:
                await service.create_booking(
                    BookingCreate(**data, request_id=uuid4()), actor
                )
                raise AssertionError("Expected an audit failure")
            except RuntimeError:
                pass
        finally:
            service.audit = original_audit
        assert await db.bookings.count_documents({"status": "pending"}) == 0
        assert await db.booking_inventory.count_documents({"reserved": {"$ne": 0}}) == 0
        print("PASS: a failed write rolls back the booking and all nightly inventory")
        print("REAL MONGODB BOOKING CHECKS PASSED")
    finally:
        if db_name.startswith("smartstay_booking_test_"):
            await client.drop_database(db_name)
        db_manager.client, db_manager.db = previous
        client.close()


if __name__ == "__main__":
    asyncio.run(run())
