from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

# Giới hạn theo đúng đặc tả Giai đoạn 3
MAX_POI_IMAGES = 8
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB (5,242,880 bytes)
DEFAULT_GEOFENCE_RADIUS = 30.0


class POIImageItem(BaseModel):
    url: str = Field(..., min_length=5, max_length=500)
    size_bytes: int = Field(
        ...,
        gt=0,
        le=MAX_IMAGE_SIZE,
        description="Kích thước ảnh tối đa 5 MB (5,242,880 bytes)",
    )
    caption: Optional[str] = Field(default=None, max_length=200)


class POIPayload(BaseModel):
    name: str = Field(..., min_length=3, max_length=180, description="Tên Homestay/Khách sạn (Tiếng Việt)")
    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Mô tả chi tiết & hướng dẫn nhận phòng (Tiếng Việt)",
    )
    category: Literal["homestay", "hotel", "resort", "villa", "boutique"] = "homestay"
    address: str = Field(..., min_length=5, max_length=300)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    images: List[POIImageItem] = Field(
        default_factory=list,
        max_length=MAX_POI_IMAGES,
        description="Danh sách tối đa 8 hình ảnh",
    )
    geofence_radius: float = Field(default=DEFAULT_GEOFENCE_RADIUS, ge=5.0, le=1000.0)
    trigger_radius: float = Field(default=DEFAULT_GEOFENCE_RADIUS, ge=5.0, le=1000.0)
    audio_priority: int = Field(default=10, ge=1, le=100)

    @field_validator("images")
    @classmethod
    def validate_max_images(cls, v: List[POIImageItem]) -> List[POIImageItem]:
        if len(v) > MAX_POI_IMAGES:
            raise ValueError(f"Maximum {MAX_POI_IMAGES} images allowed per POI")
        return v


class OwnerSubmissionCreateRequest(BaseModel):
    submission_type: Literal["create", "update"] = "create"
    target_poi_id: Optional[str] = Field(default=None, description="ID của POI nếu là cập nhật")
    poi_data: POIPayload


class AdminSubmissionReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]
    admin_note: str = Field(..., min_length=2, max_length=500)


class MenuItemCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Tên hạng phòng")
    price: int = Field(..., gt=0, description="Giá phòng (VNĐ/đêm)")
    services: List[str] = Field(default_factory=list, description="Dịch vụ đi kèm (ăn sáng, xe đưa đón...)")
    capacity: int = Field(default=2, ge=1, le=20)
    is_available: bool = True


class POILocalizationUpsertRequest(BaseModel):
    lang: str = Field(..., min_length=2, max_length=10, description="Mã ngôn ngữ: en, ja, ko, zh, fr...")
    name: str = Field(..., min_length=2, max_length=200)
    description: str = Field(..., min_length=5, max_length=5000)
    audio_url: Optional[str] = Field(default=None, max_length=500)
