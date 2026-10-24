from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Registration(StrictModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=8, max_length=72)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value):
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.get_secret_value().encode()) > 72:
            raise ValueError("Password exceeds 72 UTF-8 bytes")
        return value


class Login(StrictModel):
    username: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(max_length=1024)
    mode: Literal["cookie", "bearer"] = "cookie"


class Refresh(StrictModel):
    refresh_token: SecretStr | None = None


class OwnerRegistration(Registration):
    email: str = Field(
        min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    phone: str = Field(min_length=6, max_length=30, pattern=r"^[+0-9 ()-]+$")
    property_name: str = Field(min_length=1, max_length=200)
    property_address: str = Field(min_length=1, max_length=500)
    national_id: SecretStr = Field(min_length=6, max_length=24)

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value):
        if not value.get_secret_value().isalnum():
            raise ValueError("Identity number must contain letters or digits only")
        return value
