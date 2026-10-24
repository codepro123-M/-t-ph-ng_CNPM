from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError

from app.admin.bootstrap import ensure_auth_indexes
from app.auth.schemas import Login, Refresh, Registration
from app.core.audit import audit, transaction
from app.core.database import get_db
from app.core.rbac import get_current_user
from app.core.security import decode_token, hash_password, utcnow
from app.core.sessions import (
    check_csrf,
    clear_cookies,
    extract_refresh,
    load_state,
    login_user,
    public_user,
    rate_limit,
    revoke_session,
    rotate_refresh,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
COLLECTION = "auth_users"
__all__ = ["router", "ensure_auth_indexes", "COLLECTION"]


@router.post("/register", status_code=201)
async def register(payload: Registration, request: Request):
    await rate_limit(request, "register", limit=20, seconds=3600)
    doc = {
        "username": payload.username,
        "full_name": payload.full_name,
        "password_hash": await hash_password(payload.password.get_secret_value()),
        "role": "user",
        "is_active": True,
        "is_verified": False,
        "is_poi_owner_verified": False,
        "auth_version": 1,
        "created_at": utcnow(),
    }
    try:
        async with transaction() as session:
            result = await get_db()[COLLECTION].insert_one(doc, session=session)
            await audit(
                "user.register",
                COLLECTION,
                result.inserted_id,
                {"sub": str(result.inserted_id), "realm": COLLECTION},
                session=session,
            )
    except DuplicateKeyError:
        raise HTTPException(409, "Username already exists") from None
    return public_user(doc)


@router.post("/login")
async def login(
    request: Request, response: Response, form: OAuth2PasswordRequestForm = Depends()
):
    if set(form.scopes) - {"admin"}:
        raise HTTPException(
            400,
            "Only the admin scope is supported to select the admin account directory",
        )
    realm = "admin_users" if "admin" in form.scopes else COLLECTION
    return await login_user(
        request, response, form.username, form.password, realm, "bearer"
    )


@router.post("/session")
async def cookie_login(payload: Login, request: Request, response: Response):
    return await login_user(
        request,
        response,
        payload.username,
        payload.password.get_secret_value(),
        COLLECTION,
        payload.mode,
    )


@router.post("/refresh")
async def refresh(request: Request, response: Response, payload: Refresh | None = None):
    return await rotate_refresh(request, response, payload)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, payload: Refresh | None = None):
    token, from_cookie = extract_refresh(request, payload)
    claims = decode_token(token, "refresh")
    state = await load_state(claims)
    if from_cookie:
        check_csrf(request, state)
    await revoke_session(claims)
    clear_cookies(response)


@router.get("/me")
async def me(response: Response, user=Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {
        "id": user["sub"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
        "is_active": True,
        "is_verified": user["is_verified"],
        "is_poi_owner_verified": user["is_poi_owner_verified"],
        "realm": user["realm"],
        "permissions": user["permissions"],
        "priority": user["priority"],
    }
