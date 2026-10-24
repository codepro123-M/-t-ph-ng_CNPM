from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.auth.schemas import StrictModel
from app.content.schemas import valid_id

BookingStatus = Literal["pending", "confirmed", "cancelled", "completed"]


def business_today():
    # Hotel dates follow Vietnam time, regardless of the container timezone.
    return datetime.now(timezone(timedelta(hours=7))).date()


class StayDates(StrictModel):
    poi_id: str
    room_type_id: str
    check_in: date
    check_out: date
    guests: int = Field(default=2, ge=1, le=100)
    validate_ids = field_validator("poi_id", "room_type_id")(valid_id)

    @model_validator(mode="after")
    def valid_stay(self):
        today = business_today()
        if self.check_in < today:
            raise ValueError("Check-in must be today or later")
        if self.check_in > today + timedelta(days=365):
            raise ValueError("Bookings open at most 365 days ahead")
        if not 1 <= (self.check_out - self.check_in).days <= 30:
            raise ValueError("A stay must last between 1 and 30 nights")
        return self


class BookingCreate(StayDates):
    request_id: UUID
    contact_name: str = Field(min_length=1, max_length=100)
    email: str = Field(
        min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    phone: str = Field(min_length=6, max_length=30, pattern=r"^[+0-9 ()-]+$")
    notes: str = Field(default="", max_length=1000)


class CancelBooking(StrictModel):
    expected_revision: int = Field(ge=1)


class UpdateBooking(StrictModel):
    expected_revision: int = Field(ge=1)
    status: Literal["confirmed", "cancelled", "completed"]
