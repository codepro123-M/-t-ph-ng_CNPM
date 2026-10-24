from app.core.database import get_db


async def ensure_booking_indexes():
    db = get_db()
    await db["bookings"].create_index("code", unique=True)
    await db["bookings"].create_index(
        [("customer_id", 1), ("request_id", 1)], unique=True
    )
    await db["bookings"].create_index([("customer_id", 1), ("created_at", -1)])
    await db["bookings"].create_index([("status", 1), ("created_at", -1)])
    await db["booking_inventory"].create_index([("room_type_id", 1), ("night", 1)])
