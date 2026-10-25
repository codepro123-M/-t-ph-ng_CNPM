"""Shared cryptographic primitives; session and RBAC checks live in their modules."""

import hashlib
import secrets
from datetime import datetime, timezone

import bcrypt
import jwt
from bson import ObjectId
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

JWT_ALGORITHM = "HS256"
_DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt(rounds=12))


def utcnow():
    return datetime.now(timezone.utc)


def random_id():
    return secrets.token_urlsafe(32)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def unauthorized():
    return HTTPException(
        401, "Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"}
    )


async def hash_password(password):
    raw = password.encode("utf-8")
    if not 8 <= len(raw) <= 72:
        raise HTTPException(422, "Password must contain 8-72 UTF-8 bytes")
    return (
        await run_in_threadpool(bcrypt.hashpw, raw, bcrypt.gensalt(rounds=12))
    ).decode()


async def verify_password(password, password_hash):
    raw = password.encode("utf-8")
    valid_length = 1 <= len(raw) <= 72
    try:
        valid = await run_in_threadpool(
            bcrypt.checkpw,
            raw if valid_length else b"invalid-length",
            password_hash.encode() if password_hash else _DUMMY_HASH,
        )
    except (ValueError, TypeError):
        return False
    return bool(valid and valid_length and password_hash)


def encode_token(payload, token_type):
    secret = (
        settings.JWT_SECRET if token_type == "access" else settings.REFRESH_TOKEN_SECRET
    )
    return jwt.encode(
        payload
        | {
            "type": token_type,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        },
        secret,
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token, token_type):
    secret = (
        settings.JWT_SECRET if token_type == "access" else settings.REFRESH_TOKEN_SECRET
    )
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "require": [
                    "sub",
                    "realm",
                    "sid",
                    "jti",
                    "type",
                    "iss",
                    "aud",
                    "iat",
                    "nbf",
                    "exp",
                ]
            },
        )
        if (
            claims["type"] != token_type
            or claims["realm"] not in {"auth_users", "admin_users"}
            or not isinstance(claims["sub"], str)
            or not ObjectId.is_valid(claims["sub"])
            or any(
                not isinstance(claims[key], str) or not claims[key]
                for key in ("sid", "jti")
            )
            or any(type(claims[key]) is not int for key in ("iat", "nbf", "exp"))
            or claims["exp"] <= claims["iat"]
        ):
            raise ValueError("Invalid claims")
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise unauthorized() from None
