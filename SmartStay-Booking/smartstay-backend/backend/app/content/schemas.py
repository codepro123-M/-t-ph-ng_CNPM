"""Vietnamese source data; media fields contain managed asset IDs, never paths."""

from decimal import Decimal
from typing import Literal

from bson import ObjectId
from pydantic import AliasChoices, Field, field_validator, model_validator

from app.auth.schemas import StrictModel
from app.core.config import MAX_POI_IMAGES

Category = Literal[
    "hotel",
    "homestay",
    "resort",
    "hostel",
    "apartment",
    "guesthouse",
    "villa",
    "boutique",
]


def valid_id(value):
    if value is not None and not ObjectId.is_valid(value):
        raise ValueError("Invalid resource ID")
    return str(value) if value is not None else None


def language_code(value):
    import re

    value = value.strip().replace("_", "-").lower()
    if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8}){0,3}", value):
        raise ValueError("Invalid language code")
    return value


class POIData(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=20000)
    check_in_instructions: str = Field(default="", max_length=10000)
    category: Category = "homestay"
    address: str = Field(min_length=1, max_length=500)
    latitude: float = Field(
        ge=-90,
        le=90,
        allow_inf_nan=False,
        validation_alias=AliasChoices("latitude", "lat"),
    )
    longitude: float = Field(
        ge=-180,
        le=180,
        allow_inf_nan=False,
        validation_alias=AliasChoices("longitude", "lng"),
    )
    images: list[str] = Field(default_factory=list, max_length=MAX_POI_IMAGES)
    geofence_radius: float = Field(
        default=30,
        ge=1,
        le=10000,
        allow_inf_nan=False,
        validation_alias=AliasChoices("geofence_radius", "trigger_radius"),
    )
    audio_priority: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def consistent_radius_aliases(cls, value):
        if (
            isinstance(value, dict)
            and "trigger_radius" in value
            and "geofence_radius" in value
        ):
            if value["trigger_radius"] != value["geofence_radius"]:
                raise ValueError("trigger_radius and geofence_radius must match")
            value = {
                key: item for key, item in value.items() if key != "trigger_radius"
            }
        return value

    @field_validator("images")
    @classmethod
    def validate_images(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Duplicate image ID")
        return [valid_id(item) for item in value]


class POICreate(POIData):
    owner_id: str | None = None
    is_active: bool = True
    validate_owner = field_validator("owner_id")(valid_id)


class POIUpdate(StrictModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=20000)
    check_in_instructions: str | None = Field(default=None, max_length=10000)
    category: Category | None = None
    address: str | None = Field(default=None, min_length=1, max_length=500)
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        allow_inf_nan=False,
        validation_alias=AliasChoices("latitude", "lat"),
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        allow_inf_nan=False,
        validation_alias=AliasChoices("longitude", "lng"),
    )
    images: list[str] | None = Field(default=None, max_length=MAX_POI_IMAGES)
    geofence_radius: float | None = Field(
        default=None,
        ge=1,
        le=10000,
        allow_inf_nan=False,
        validation_alias=AliasChoices("geofence_radius", "trigger_radius"),
    )
    audio_priority: int | None = Field(default=None, ge=0, le=100)
    owner_id: str | None = None
    is_active: bool | None = None
    validate_owner = field_validator("owner_id")(valid_id)


class Submission(StrictModel):
    kind: Literal["create", "update"] = Field(
        validation_alias=AliasChoices("kind", "submission_type")
    )
    poi_id: str | None = Field(
        default=None, validation_alias=AliasChoices("poi_id", "target_poi_id")
    )
    expected_revision: int | None = Field(default=None, ge=1)
    payload: POIData = Field(validation_alias=AliasChoices("payload", "poi_data"))
    validate_poi_id = field_validator("poi_id")(valid_id)

    @model_validator(mode="after")
    def validate_target(self):
        if self.kind == "create" and (
            self.poi_id is not None or self.expected_revision is not None
        ):
            raise ValueError("Create submissions must not specify a target or revision")
        if self.kind == "update" and (
            not self.poi_id or self.expected_revision is None
        ):
            raise ValueError("Update submissions require poi_id and expected_revision")
        return self


class SubmissionReview(StrictModel):
    status: Literal["approved", "rejected"]
    admin_note: str = Field(default="", max_length=2000)


class MenuData(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    kind: Literal["room_type", "service"] = "room_type"
    price: Decimal = Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    currency: str = Field(default="VND", pattern=r"^[A-Z]{3}$")
    capacity: int = Field(default=2, ge=1, le=100)
    inventory: int = Field(default=1, ge=1, le=1000)
    amenities: list[str] = Field(
        default_factory=list,
        max_length=50,
        validation_alias=AliasChoices("amenities", "services"),
    )
    is_available: bool = True

    @field_validator("amenities")
    @classmethod
    def short_amenities(cls, value):
        if any(not item.strip() or len(item) > 160 for item in value):
            raise ValueError("Amenities must contain 1-160 characters")
        return list(dict.fromkeys(value))


class MenuCreate(MenuData):
    poi_id: str
    validate_poi_id = field_validator("poi_id")(valid_id)


class MenuUpdate(MenuData):
    expected_revision: int = Field(ge=1)


class Localization(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=20000)
    check_in_instructions: str = Field(max_length=10000)
    source_revision: int = Field(ge=1)
    audio_asset_id: str | None = None
    validate_audio_id = field_validator("audio_asset_id")(valid_id)
