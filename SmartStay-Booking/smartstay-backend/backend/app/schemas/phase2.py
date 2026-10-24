from typing import List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterOwnerRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=120)
    phone: str = Field(..., min_length=9, max_length=15)
    cccd_number: str = Field(..., min_length=9, max_length=12, pattern=r"^\d{9,12}$")
    property_name: str = Field(..., min_length=3, max_length=180)
    property_type: Literal["homestay", "hotel", "resort", "villa"] = "homestay"
    property_address: str = Field(..., min_length=5, max_length=300)
    business_license: Optional[str] = Field(default=None, max_length=60)


class ReviewRegistrationRequest(BaseModel):
    status: Literal["approved", "rejected"]
    review_note: Optional[str] = Field(default="Reviewed by Admin", max_length=500)


class CreateRoomCategoryRequest(BaseModel):
    room_name: str = Field(..., min_length=2, max_length=120)
    price_vnd: int = Field(..., gt=0)
    capacity: int = Field(default=2, ge=1, le=20)
    amenities: List[str] = Field(default_factory=list)


class SubmitOwnerContentRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    narration_script_vi: str = Field(..., min_length=10, max_length=5000)
    qr_zone_code: str = Field(..., min_length=2, max_length=60)