"""Dual-mode sessions, single-use refresh rotation, and immediate invalidation."""

import json
import secrets
from datetime import timedelta

from bson import ObjectId
from fastapi import HTTPException, Request, Response
from pymongo import ReturnDocument
from redis.exceptions import RedisError

from app.core.audit import audit, transaction
from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    settings,
)
from app.core.database import get_db, get_redis
from app.core.security import (
    decode_token,
    digest,
    encode_token,
    random_id,
    unauthorized,
    utcnow,
    verify_password,
)

ACCESS_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_SECONDS = REFRESH_TOKEN_EXPIRE_DAYS * 86400
MAX_VERSION = """
local old = redis.call('GET', KEYS[1])
if not old or tonumber(old) < tonumber(ARGV[1]) then
  redis.call('SET', KEYS[1], ARGV[1])
  return ARGV[1]
end
return old
"""
RATE_LIMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


def user_version_key(realm, user_id):
    return f"auth:user:{realm}:{user_id}"


def role_version_key(role):
    return f"auth:role:{role}"


def session_key(sid):
    return "auth:session:" + sid


async def publish_version(key, version):
    try:
        return int(await get_redis().eval(MAX_VERSION, 1, key, int(version)))
    except RedisError:
        raise HTTPException(503, "Authentication cache unavailable") from None


async def next_role_version(name):
    try:
        previous = await get_redis().get(role_version_key(name))
        return int(previous or 0) + 1
    except RedisError:
        raise HTTPException(503, "Authentication cache unavailable") from None


async def rate_limit(request, scope, identity="", *, limit=15, seconds=60):
    ip = request.client.host if request.client else "unknown"
    key = f"auth:rate:{scope}:{digest(ip + ':' + identity)}"
    try:
        count = int(await get_redis().eval(RATE_LIMIT, 1, key, seconds))
    except RedisError:
        raise HTTPException(503, "Authentication cache unavailable") from None
    if count > limit:
        raise HTTPException(
            429,
            "Too many attempts; try again later",
            headers={"Retry-After": str(seconds)},
        )


def check_origin(request: Request):
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") not in settings.trusted_origins:
        raise HTTPException(403, "Untrusted request origin")


def check_csrf(request: Request, state: dict):
    check_origin(request)
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get("csrf_token", "")
    if (
        not header
        or not cookie
        or not header.isascii()
        or not cookie.isascii()
        or not secrets.compare_digest(header, cookie)
        or not secrets.compare_digest(digest(header), state.get("csrf_hash", ""))
    ):
        raise HTTPException(403, "A matching X-CSRF-Token header is required")


async def load_state(claims):
    try:
        raw = await get_redis().get(session_key(claims["sid"]))
    except RedisError:
        raise HTTPException(503, "Authentication cache unavailable") from None
    if not raw:
        raise unauthorized()
    try:
        state = json.loads(raw)
        if not isinstance(state, dict):
            raise ValueError("Invalid session")
    except (ValueError, TypeError):
        raise HTTPException(503, "Authentication cache unavailable") from None
    if state.get("user_id") != claims["sub"] or state.get("realm") != claims["realm"]:
        raise unauthorized()
    return state


async def role_for(user):
    role = await get_db()["roles"].find_one({"name": user.get("role", "user")})
    if not role:
        raise unauthorized()
    return role


def public_user(user, realm=None):
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user.get("role", "user"),
        "is_active": user.get("is_active", True),
        "is_verified": bool(user.get("is_verified", False)),
        "is_poi_owner_verified": bool(user.get("is_poi_owner_verified", False)),
        **({"realm": realm} if realm else {}),
    }


async def access_for(user, realm, sid):
    role = await role_for(user)
    version = int(user.get("auth_version", 1))
    role_version = int(role.get("version", 1))
    # Never lower epochs after another process has invalidated an old token.
    if await publish_version(user_version_key(realm, user["_id"]), version) != version:
        raise unauthorized()
    if (
        await publish_version(role_version_key(role["name"]), role_version)
        != role_version
    ):
        raise unauthorized()
    now = utcnow()
    return encode_token(
        {
            "sub": str(user["_id"]),
            "realm": realm,
            "sid": sid,
            "jti": random_id(),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(seconds=ACCESS_SECONDS),
            "role": role["name"],
            "roles": [role["name"]],
            "priority": role["priority"],
            "permissions": role["permissions"],
            "role_version": role_version,
            "auth_version": version,
            "username": user["username"],
            "full_name": user["full_name"],
            "is_verified": bool(user.get("is_verified", False)),
            "is_poi_owner_verified": bool(user.get("is_poi_owner_verified", False)),
        },
        "access",
    )


def refresh_for(user, realm, sid, jti, expires):
    now = utcnow()
    return encode_token(
        {
            "sub": str(user["_id"]),
            "realm": realm,
            "sid": sid,
            "jti": jti,
            "iat": now,
            "nbf": now,
            "exp": expires,
        },
        "refresh",
    )


def set_cookies(response, access, refresh, csrf, refresh_seconds):
    for name, value, age, httponly in (
        ("access_token", access, ACCESS_SECONDS, True),
        ("refresh_token", refresh, refresh_seconds, True),
        ("csrf_token", csrf, refresh_seconds, False),
    ):
        response.set_cookie(
            name,
            value,
            max_age=age,
            secure=True,
            httponly=httponly,
            samesite="lax",
            path="/",
        )


def clear_cookies(response):
    for name in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(
            name, path="/", secure=True, httponly=name != "csrf_token", samesite="lax"
        )


def session_response(user, realm, access, refresh, mode):
    result = {
        "user": public_user(user, realm),
        "expires_in": ACCESS_SECONDS,
        "mode": mode,
    }
    if mode == "bearer":
        result.update(access_token=access, refresh_token=refresh, token_type="bearer")
    return result


async def login_user(
    request: Request, response: Response, username, password, realm, mode
):
    check_origin(request)
    await rate_limit(request, "login", username.strip().lower())
    await rate_limit(request, "login-ip", limit=100)
    user = await get_db()[realm].find_one({"username": username.strip().lower()})
    valid = await verify_password(password, user.get("password_hash") if user else None)
    if not valid or not user or not user.get("is_active", True):
        raise unauthorized()
    if (
        mode == "cookie"
        and request.url.scheme != "https"
        and request.headers.get("x-forwarded-proto") != "https"
    ):
        raise HTTPException(
            400,
            "Cookie login requires HTTPS. Use https://localhost:8443 or mode=bearer.",
        )
    sid, jti, csrf = random_id(), random_id(), random_id()
    expires = utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    access = await access_for(user, realm, sid)
    refresh = refresh_for(user, realm, sid, jti, expires)
    async with transaction() as session:
        await get_db()["refresh_sessions"].insert_one(
            {
                "_id": sid,
                "user_id": str(user["_id"]),
                "realm": realm,
                "refresh_hash": digest(jti),
                "expires_at": expires,
                "revoked": False,
            },
            session=session,
        )
        await audit(
            "login",
            realm,
            user["_id"],
            {"sub": str(user["_id"]), "realm": realm},
            session=session,
        )
    state = json.dumps(
        {"user_id": str(user["_id"]), "realm": realm, "csrf_hash": digest(csrf)}
    )
    try:
        await get_redis().set(session_key(sid), state, ex=REFRESH_SECONDS, nx=True)
    except RedisError:
        raise HTTPException(503, "Authentication cache unavailable") from None
    if mode == "cookie":
        set_cookies(response, access, refresh, csrf, REFRESH_SECONDS)
    response.headers["Cache-Control"] = "no-store"
    return session_response(user, realm, access, refresh, mode)


async def revoke_session(claims, action="logout"):
    # Deleting an allowlist entry makes logout effective even before DB commit.
    try:
        await get_redis().delete(session_key(claims["sid"]))
    except RedisError:
        raise HTTPException(503, "Authentication cache unavailable") from None
    async with transaction() as session:
        await get_db()["refresh_sessions"].update_one(
            {"_id": claims["sid"], "user_id": claims["sub"], "realm": claims["realm"]},
            {"$set": {"revoked": True}},
            session=session,
        )
        await audit(action, "refresh_sessions", claims["sid"], claims, session=session)


def extract_refresh(request, body):
    if body and body.refresh_token:
        return body.refresh_token.get_secret_value(), False
    auth = request.headers.get("authorization")
    if auth:
        scheme, _, value = auth.partition(" ")
        if scheme.lower() != "bearer" or not value.strip():
            raise unauthorized()
        return value.strip(), False
    token = request.cookies.get("refresh_token")
    if not token:
        raise unauthorized()
    return token, True


async def rotate_refresh(request, response, body=None):
    token, cookie_mode = extract_refresh(request, body)
    claims = decode_token(token, "refresh")
    state = await load_state(claims)
    if cookie_mode:
        check_csrf(request, state)
    now = utcnow()
    user = await get_db()[claims["realm"]].find_one({"_id": ObjectId(claims["sub"])})
    if not user or not user.get("is_active", True):
        await revoke_session(claims, "session.disabled")
        raise unauthorized()
    new_jti = random_id()
    # A CAS update allows exactly one request to rotate this refresh token.
    async with transaction() as session:
        old = await get_db()["refresh_sessions"].find_one_and_update(
            {
                "_id": claims["sid"],
                "user_id": claims["sub"],
                "realm": claims["realm"],
                "refresh_hash": digest(claims["jti"]),
                "revoked": False,
                "expires_at": {"$gt": now},
            },
            {"$set": {"refresh_hash": digest(new_jti), "rotated_at": now}},
            return_document=ReturnDocument.BEFORE,
            session=session,
        )
        if old:
            await audit(
                "refresh", "refresh_sessions", claims["sid"], claims, session=session
            )
    if not old:
        await revoke_session(claims, "refresh.reuse")
        raise unauthorized()
    access = await access_for(user, claims["realm"], claims["sid"])
    refresh = refresh_for(user, claims["realm"], claims["sid"], new_jti, claims["exp"])
    # XX prevents a concurrent logout from resurrecting a revoked session.
    remaining = max(1, int(claims["exp"] - now.timestamp()))
    try:
        active = await get_redis().set(
            session_key(claims["sid"]), json.dumps(state), xx=True, ex=remaining
        )
    except RedisError:
        raise HTTPException(503, "Authentication cache unavailable") from None
    if not active:
        raise unauthorized()
    if cookie_mode:
        set_cookies(response, access, refresh, request.cookies["csrf_token"], remaining)
    response.headers["Cache-Control"] = "no-store"
    return session_response(
        user, claims["realm"], access, refresh, "cookie" if cookie_mode else "bearer"
    )
