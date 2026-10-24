"""Versioned, purpose-separated Fernet encryption for owner identity numbers."""

import base64
from datetime import timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import UNSAFE_PLACEHOLDERS, settings
from app.core.security import utcnow


def _fernet() -> Fernet:
    if (
        settings.SECRET_KEY.strip() in UNSAFE_PLACEHOLDERS
        or len(settings.SECRET_KEY.strip()) < 32
    ):
        raise RuntimeError(
            "Configure a strong SECRET_KEY before storing PII. Run configure_phase2.py."
        )
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"smartstay-pii-v1",
        info=b"owner-national-id",
    ).derive(settings.SECRET_KEY.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_pii(value: str) -> str:
    return "v1:" + _fernet().encrypt(value.encode()).decode()


def decrypt_pii(value: str) -> str:
    if not value.startswith("v1:"):
        raise ValueError("Unsupported PII encryption version")
    return _fernet().decrypt(value[3:].encode()).decode()


def pii_is_live(user: dict) -> bool:
    expires = user.get("pii_expires_at")
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return bool(user.get("national_id_encrypted") and expires and expires > utcnow())
