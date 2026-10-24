"""JWT claims + Redis epochs; guards do not query MongoDB."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from redis.exceptions import RedisError

from app.core.database import get_redis
from app.core.security import decode_token, unauthorized
from app.core.sessions import check_csrf, load_state, role_version_key, user_version_key

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scopes={"admin": "Use the admin/owner account directory"},
    auto_error=False,
)


async def get_current_user(request: Request, bearer=Depends(oauth2_scheme)):
    authorization = request.headers.get("authorization")
    from_cookie = authorization is None
    if authorization is not None:
        if authorization.partition(" ")[0].lower() != "bearer" or not bearer:
            raise unauthorized()
        token = bearer
    else:
        token = request.cookies.get("access_token")
    if not token:
        raise unauthorized()
    claims = decode_token(token, "access")
    if not isinstance(claims.get("permissions"), list) or not isinstance(
        claims.get("role"), str
    ):
        raise unauthorized()
    state = await load_state(claims)
    try:
        user_version, role_version = await get_redis().mget(
            user_version_key(claims["realm"], claims["sub"]),
            role_version_key(claims["role"]),
        )
    except RedisError:
        raise HTTPException(503, "Authentication cache unavailable") from None
    if str(user_version) != str(claims.get("auth_version")) or str(role_version) != str(
        claims.get("role_version")
    ):
        raise unauthorized()
    if from_cookie and request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_csrf(request, state)
    return claims


def require_permission(permission):
    async def guard(user=Depends(get_current_user)):
        if permission not in user["permissions"]:
            raise HTTPException(403, "Permission required: " + permission)
        return user

    return guard


def require_role(role):
    async def guard(user=Depends(get_current_user)):
        if role not in user.get("roles", []):
            raise HTTPException(403, "Role required: " + role)
        return user

    return guard


def require_any_permission(*permissions):
    async def guard(user=Depends(get_current_user)):
        if not set(permissions).intersection(user["permissions"]):
            raise HTTPException(403, "Insufficient permissions")
        return user

    return guard


def require_verified_owner_permission(permission):
    async def guard(user=Depends(require_permission(permission))):
        if (
            user["realm"] != "admin_users"
            or not user.get("is_verified")
            or not user.get("is_poi_owner_verified")
        ):
            raise HTTPException(403, "Owner verification is required")
        return user

    return guard
