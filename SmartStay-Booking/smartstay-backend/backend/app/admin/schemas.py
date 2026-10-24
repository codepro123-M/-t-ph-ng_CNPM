from typing import Literal

from pydantic import Field, SecretStr, field_validator

from app.auth.schemas import Registration, StrictModel
from app.core.permissions import PERMISSIONS


class ReviewRegistration(StrictModel):
    status: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=500)


class RoleCreate(StrictModel):
    name: str = Field(min_length=3, max_length=50, pattern=r"^[a-z][a-z0-9_]+$")
    priority: int = Field(ge=1, le=1000)
    permissions: list[str] = Field(max_length=64)

    @field_validator("permissions")
    @classmethod
    def known_permissions(cls, values):
        if set(values) - set(PERMISSIONS):
            raise ValueError("Unknown permission")
        return sorted(set(values))


class RoleUpdate(StrictModel):
    priority: int = Field(ge=1, le=1000)
    permissions: list[str] = Field(max_length=64)
    validate_permissions = field_validator("permissions")(
        RoleCreate.known_permissions.__func__
    )


class UserCreate(Registration):
    role: str = "user"


class UserUpdate(StrictModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, min_length=3, max_length=50)
    is_active: bool | None = None
    password: SecretStr | None = Field(default=None, min_length=8, max_length=72)
