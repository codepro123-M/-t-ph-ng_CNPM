import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError

from app.bookings import service
from app.bookings.schemas import (
    BookingCreate,
    BookingStatus,
    CancelBooking,
    StayDates,
    UpdateBooking,
)
from app.core.database import get_db
from app.core.rbac import get_current_user, require_permission
from app.core.sessions import rate_limit

router = APIRouter(tags=["bookings"])


async def customer(user=Depends(get_current_user)):
    if user["realm"] != "auth_users":
        raise HTTPException(403, "Sign in with a customer account to book a room")
    return user


async def booking_reader(user=Depends(require_permission("booking.read"))):
    if user["realm"] != "admin_users":
        raise HTTPException(403, "Administrator account required")
    return user


async def booking_editor(user=Depends(require_permission("booking.update"))):
    if user["realm"] != "admin_users":
        raise HTTPException(403, "Administrator account required")
    return user


@router.get("/bookings/availability")
async def availability(
    poi_id: str,
    room_type_id: str,
    check_in: date,
    check_out: date,
    guests: int = Query(2, ge=1, le=100),
):
    try:
        payload = StayDates(
            poi_id=poi_id,
            room_type_id=room_type_id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
        )
    except ValidationError:
        raise HTTPException(
            422, "Check room IDs, dates, the 30-night limit and guest count"
        ) from None
    return await service.availability(payload)


@router.post("/bookings", status_code=201)
async def create(
    payload: BookingCreate,
    request: Request,
    response: Response,
    actor=Depends(customer),
):
    response.headers["Cache-Control"] = "no-store"
    await rate_limit(request, "booking-create", limit=60, seconds=3600)
    return await service.create_booking(payload, actor)


@router.get("/bookings")
async def mine(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(customer),
):
    response.headers["Cache-Control"] = "no-store"
    return await service.list_bookings({"customer_id": actor["sub"]}, page, limit)


@router.get("/bookings/{booking_id}")
async def detail(booking_id: str, response: Response, actor=Depends(customer)):
    response.headers["Cache-Control"] = "no-store"
    row = await get_db()["bookings"].find_one(
        {"_id": service.oid(booking_id), "customer_id": actor["sub"]}
    )
    if not row:
        raise HTTPException(404, "Booking not found")
    return service.present(row)


@router.patch("/bookings/{booking_id}/cancel")
async def cancel(booking_id: str, payload: CancelBooking, actor=Depends(customer)):
    return await service.update_booking(booking_id, payload, actor, customer=True)


@router.get("/admin/bookings")
async def all_bookings(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: BookingStatus | None = None,
    search: str = Query("", max_length=100),
    actor=Depends(booking_reader),
):
    response.headers["Cache-Control"] = "no-store"
    query = {"status": status} if status else {}
    if search.strip():
        term = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [
            {field: term}
            for field in ("code", "contact_name", "email", "phone", "property_name")
        ]
    return await service.list_bookings(query, page, limit, admin=True)


@router.patch("/admin/bookings/{booking_id}")
async def update(
    booking_id: str, payload: UpdateBooking, actor=Depends(booking_editor)
):
    return await service.update_booking(booking_id, payload, actor)
