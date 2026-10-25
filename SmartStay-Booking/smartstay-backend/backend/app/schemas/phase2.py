from typing import List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

class OwnerRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=120)
    phone: str = Field(..., min_length=8, max_length=20)
    cccd_number: str = Field(..., min_length=9, max_length=15)
    property_name: str = Field(..., min_length=2, max_length=150)
    property_type: Literal["homestay", "hotel", "resort", "villa"] = "homestay"
    property_address: str = Field(..., min_length=5, max_length=255)
    business_license: Optional[str] = None

class RegistrationReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]
    review_note: Optional[str] = Field(default=None, max_length=500)

class RolePermissionsUpdateRequest(BaseModel):
    permissions: List[str]
    description: Optional[str] = None

class OwnerRoomCreateRequest(BaseModel):
    room_name: str = Field(..., min_length=2, max_length=120)
    room_type: str = Field(default="deluxe")
    price_vnd: int = Field(..., gt=0)
    capacity: int = Field(default=2, ge=1, le=20)

class OwnerPostSubmitRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    narration_text: str = Field(..., min_length=10, max_length=5000)
    language: str = Field(default="vi")
