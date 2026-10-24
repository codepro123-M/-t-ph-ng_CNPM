"""Password hashing and strictly separated access/refresh JWTs."""

import hashlib
import secrets
from datetime import datetime, timezone

import bcrypt
import jwt
from bson import ObjectId
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

ALGORITHM = "HS256"
DUMMY_HASH = bcrypt.hashpw(b"dummy-password-only", bcrypt.gensalt())


def utcnow():
    return datetime.now(timezone.utc)


def unauthorized():
    return HTTPException(
        401, "Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"}
    )


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if not 8 <= len(raw) <= 72:
        raise HTTPException(422, "Password must contain 8-72 UTF-8 bytes")
    return (await run_in_threadpool(bcrypt.hashpw, raw, bcrypt.gensalt())).decode()


async def verify_password(password: str, password_hash: str | None) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raw = b"invalid-overlong-password"
    try:
        valid = await run_in_threadpool(
            bcrypt.checkpw, raw, password_hash.encode() if password_hash else DUMMY_HASH
        )
    except (ValueError, TypeError):
        return False
    return bool(valid and password_hash and len(password.encode()) <= 72)


def encode_token(claims: dict, token_type: str) -> str:
    secret = (
        settings.JWT_SECRET if token_type == "access" else settings.REFRESH_TOKEN_SECRET
    )
    return jwt.encode(
        claims
        | {
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "type": token_type,
        },
        secret,
        algorithm=ALGORITHM,
    )


def decode_token(token: str, token_type: str) -> dict:
    secret = (
        settings.JWT_SECRET if token_type == "access" else settings.REFRESH_TOKEN_SECRET
    )
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "require": [
                    "sub",
                    "exp",
                    "iat",
                    "nbf",
                    "jti",
                    "sid",
                    "realm",
                    "type",
                    "iss",
                    "aud",
                ]
            },
        )
        if (
            claims["type"] != token_type
            or not isinstance(claims["sub"], str)
            or not ObjectId.is_valid(claims["sub"])
            or claims["realm"] not in {"auth_users", "admin_users"}
            or not all(
                isinstance(claims[k], str) and 16 <= len(claims[k]) <= 128
                for k in ("sid", "jti")
            )
        ):
            raise ValueError("claims")
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise unauthorized() from None


def random_id() -> str:
    return secrets.token_urlsafe(32)
