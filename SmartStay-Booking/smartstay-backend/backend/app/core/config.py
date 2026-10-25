import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# ===== KEY CONSTANTS =====
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
VOICE_CATALOG_TTL_SECONDS = 6 * 3600
MAX_CONCURRENT_TTS = 3
AUDIO_TASK_HEARTBEAT_SECONDS = 5
AUDIO_TASK_STALE_AFTER_SECONDS = 300
AUDIO_TASK_RETENTION_DAYS = 14
PII_RETENTION_DAYS = 180
MAX_POI_IMAGES = 8
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
ON_DEMAND_RATE_LIMIT = 30
HOTSET_MAX_POI_IDS = 10
OWNER_DAILY_LIMIT = 10

UNSAFE_PLACEHOLDERS = {
    "",
    "changeme",
    "secret",
    "dev-jwt-secret-key-change-in-production-32chars",
    "dev-refresh-secret-key-change-in-prod-32chars",
    "dev-fernet-and-app-secret-key-change-in-prod",
}

VALID_BOOTSTRAP_MODES = {"disabled", "auto", "env_only"}


class Settings(BaseSettings):
    APP_ENV: str = "development"
    MONGODB_URI: str = "mongodb://localhost:27017/?replicaSet=rs0"
    MONGODB_DB_NAME: str = "smart_stay_tourism"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "dev-jwt-secret-key-change-in-production-32chars"
    REFRESH_TOKEN_SECRET: str = "dev-refresh-secret-key-change-in-prod-32chars"
    SECRET_KEY: str = "dev-fernet-and-app-secret-key-change-in-prod"
    SUPERADMIN_BOOTSTRAP_MODE: str = "auto"
    SUPERADMIN_USERNAME: str = ""
    SUPERADMIN_PASSWORD: str = ""
    JWT_ISSUER: str = "smart-stay-backend"
    JWT_AUDIENCE: str = "smart-stay-api"
    TRUSTED_ORIGINS: str = "https://localhost:8443,https://127.0.0.1:8443,http://localhost:8001,http://127.0.0.1:8001"
    PII_CLEANUP_INTERVAL_SECONDS: int = Field(default=3600, ge=10, le=86400)
    CONTENT_MEDIA_DIR: Path = BASE_DIR.parent / "runtime_data" / "content-media"
    CONTENT_CLEANUP_INTERVAL_SECONDS: int = Field(default=30, ge=1, le=3600)
    CONTENT_MEDIA_GRACE_SECONDS: int = Field(default=86400, ge=3600, le=604800)
    CONTENT_QUERY_TIMEOUT_MS: int = Field(default=10000, ge=100, le=60000)
    MAX_AUDIO_SIZE_BYTES: int = Field(
        default=25 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024
    )
    TRANSLATION_PROVIDER: Literal["auto", "google", "mymemory"] = "auto"
    TRANSLATION_CACHE_TTL_SECONDS: int = Field(
        default=30 * 86400, ge=60, le=365 * 86400
    )
    TRANSLATION_GOOGLE_COOLDOWN_SECONDS: int = Field(default=900, ge=60, le=86400)
    MYMEMORY_EMAIL: str = Field(default="", max_length=254)

    MEDIA_BACKEND: str = "local"
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_SESSION_TOKEN: str = ""
    S3_ADDRESSING_STYLE: str = "path"
    S3_HEALTH_PREFIX: str = "_healthchecks"
    S3_CONNECT_TIMEOUT_SECONDS: float = Field(default=2, ge=0.1, le=10)
    S3_READ_TIMEOUT_SECONDS: float = Field(default=2, ge=0.1, le=10)
    S3_HEALTH_CACHE_TTL_SECONDS: float = Field(default=30, ge=0, le=300)
    S3_CA_BUNDLE: str = ""
    STATIC_DIR: Path = BASE_DIR / "static"
    MAP_PACK_DATA_DIR: Path = Path(
        os.getenv("MAP_PACK_DATA_DIR", str(BASE_DIR / "static" / "maps"))
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def validate_security_and_bootstrap(self) -> None:
        self.validate_media_storage()
        if self.CONTENT_MEDIA_DIR.resolve().is_relative_to(self.STATIC_DIR.resolve()):
            raise RuntimeError(
                "CONTENT_MEDIA_DIR must be outside the public STATIC_DIR."
            )
        if self.SUPERADMIN_BOOTSTRAP_MODE not in VALID_BOOTSTRAP_MODES:
            raise RuntimeError(
                f"Invalid SUPERADMIN_BOOTSTRAP_MODE='{self.SUPERADMIN_BOOTSTRAP_MODE}'. "
                f"Must be one of {VALID_BOOTSTRAP_MODES}."
            )

        if self.APP_ENV.lower() not in {"dev", "development", "test"}:
            for key_name in ("JWT_SECRET", "REFRESH_TOKEN_SECRET", "SECRET_KEY"):
                val = getattr(self, key_name, "").strip()
                if val in UNSAFE_PLACEHOLDERS or len(val) < 32:
                    raise RuntimeError(
                        f"Security Guard Fail-Fast: {key_name} is unsafe or too short "
                        f"in non-dev environment ({self.APP_ENV})."
                    )
            if len({self.JWT_SECRET, self.REFRESH_TOKEN_SECRET, self.SECRET_KEY}) != 3:
                raise RuntimeError("Use three different security secrets.")
            if any(
                not origin.startswith("https://") for origin in self.trusted_origins
            ):
                raise RuntimeError(
                    "TRUSTED_ORIGINS must use HTTPS outside development."
                )

    @property
    def trusted_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.TRUSTED_ORIGINS.split(",")
            if origin.strip()
        ]

    def validate_media_storage(self) -> None:
        backend = self.MEDIA_BACKEND.strip().lower()
        if backend not in {"local", "s3"}:
            raise RuntimeError("MEDIA_BACKEND must be 'local' or 's3'.")
        if backend == "local":
            return
        for name in ("S3_BUCKET", "S3_REGION", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise RuntimeError(
                    f"{name} is required and must not have outer whitespace."
                )
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.S3_BUCKET)
            or ".." in self.S3_BUCKET
        ):
            raise RuntimeError(
                "S3_BUCKET must be a DNS-compatible bucket name (3-63 characters)."
            )
        if self.S3_ADDRESSING_STYLE not in {"path", "virtual", "auto"}:
            raise RuntimeError("S3_ADDRESSING_STYLE must be path, virtual, or auto.")
        prefix = self.S3_HEALTH_PREFIX.strip("/")
        if not prefix or prefix != prefix.strip() or ".." in prefix.split("/"):
            raise RuntimeError(
                "S3_HEALTH_PREFIX must be a non-empty dedicated object prefix."
            )
        if self.S3_ENDPOINT_URL:
            try:
                endpoint = urlsplit(self.S3_ENDPOINT_URL)
                valid = (
                    endpoint.scheme in {"http", "https"}
                    and bool(endpoint.hostname)
                    and not endpoint.username
                    and not endpoint.password
                    and not endpoint.query
                    and not endpoint.fragment
                    and (endpoint.port is None or 1 <= endpoint.port <= 65535)
                    and self.S3_ENDPOINT_URL == self.S3_ENDPOINT_URL.strip()
                )
            except ValueError:
                valid = False
            if not valid:
                raise RuntimeError(
                    "S3_ENDPOINT_URL must be an HTTP(S) endpoint without credentials or query parameters."
                )
        if self.S3_CA_BUNDLE and not Path(self.S3_CA_BUNDLE).is_file():
            raise RuntimeError(
                "S3_CA_BUNDLE must point to an existing CA certificate file."
            )


settings = Settings()
