from datetime import timedelta
from typing import Literal

from bson import ObjectId
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pymongo.errors import DuplicateKeyError

from app.admin.schemas import (
    ReviewRegistration,
    RoleCreate,
    RoleUpdate,
    UserCreate,
    UserUpdate,
)
from app.auth.router import logout, me, refresh
from app.auth.schemas import Login, OwnerRegistration
from app.core.audit import audit, public_document, transaction
from app.core.config import PII_RETENTION_DAYS
from app.core.database import get_db
from app.core.permissions import PERMISSION_DOMAINS, PERMISSIONS
from app.core.pii import decrypt_pii, encrypt_pii, pii_is_live
from app.core.rbac import require_any_permission, require_permission
from app.core.security import hash_password, utcnow
from app.core.sessions import (
    login_user,
    next_role_version,
    public_user,
    publish_version,
    rate_limit,
    role_version_key,
    user_version_key,
)

router = APIRouter(prefix="/admin", tags=["admin"])
Realm = Literal["admin_users", "auth_users"]


def object_id(value):
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "Resource not found")
    return ObjectId(value)


async def get_role(name):
    role = await get_db()["roles"].find_one({"name": name})
    if not role:
        raise HTTPException(404, "Role not found")
    return role


async def touch_role(role, session):
    # Serialize assigning a role against deletion or permission changes.
    result = await get_db()["roles"].update_one(
        {"_id": role["_id"], "version": role.get("version", 1)},
        {"$inc": {"assignment_revision": 1}},
        session=session,
    )
    if not result.modified_count:
        raise HTTPException(409, "Role changed concurrently; reload and retry")


def check_target_role(actor, role):
    if actor["role"] != "super_admin" and (
        role["priority"] <= actor["priority"]
        or not set(role["permissions"]).issubset(actor["permissions"])
    ):
        raise HTTPException(403, "Cannot manage a role at or above your authority")


async def managed_user(actor, realm, user_id):
    user = await get_db()[realm].find_one({"_id": object_id(user_id)})
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("role") == "super_admin":
        raise HTTPException(
            403, "Super-admin accounts are protected from API modification"
        )
    check_target_role(actor, await get_role(user.get("role", "user")))
    return user


@router.get("/ping")
async def ping_admin():
    return {"lane": "admin", "status": "ok"}


@router.post("/auth/login", tags=["admin-auth"])
async def admin_login(payload: Login, request: Request, response: Response):
    return await login_user(
        request,
        response,
        payload.username,
        payload.password.get_secret_value(),
        "admin_users",
        payload.mode,
    )


router.add_api_route("/auth/refresh", refresh, methods=["POST"], tags=["admin-auth"])
router.add_api_route(
    "/auth/logout", logout, methods=["POST"], status_code=204, tags=["admin-auth"]
)
router.add_api_route("/auth/me", me, methods=["GET"], tags=["admin-auth"])


@router.post("/auth/register-owner", status_code=201, tags=["admin-auth"])
async def register_owner(payload: OwnerRegistration, request: Request):
    await rate_limit(request, "register-owner", limit=10, seconds=3600)
    now, user_id, registration_id = utcnow(), ObjectId(), ObjectId()
    try:
        encrypted = encrypt_pii(payload.national_id.get_secret_value())
    except RuntimeError:
        raise HTTPException(503, "PII encryption is not configured") from None
    user = {
        "_id": user_id,
        "username": payload.username,
        "full_name": payload.full_name,
        "password_hash": await hash_password(payload.password.get_secret_value()),
        "email": payload.email,
        "phone": payload.phone,
        "role": "poi_owner",
        "is_active": True,
        "is_verified": False,
        "is_poi_owner_verified": False,
        "auth_version": 1,
        "national_id_encrypted": encrypted,
        "pii_expires_at": now + timedelta(days=PII_RETENTION_DAYS),
        "created_at": now,
    }
    registration = {
        "_id": registration_id,
        "user_id": str(user_id),
        "property_name": payload.property_name,
        "property_address": payload.property_address,
        "status": "pending",
        "created_at": now,
    }
    try:
        async with transaction() as session:
            await get_db()["admin_users"].insert_one(user, session=session)
            await get_db()["poi_owner_registrations"].insert_one(
                registration, session=session
            )
            await audit(
                "owner.register",
                "poi_owner_registrations",
                registration_id,
                {"sub": str(user_id), "realm": "admin_users"},
                session=session,
            )
    except DuplicateKeyError:
        raise HTTPException(409, "Username already exists") from None
    return {
        "user": public_user(user),
        "registration_id": str(registration_id),
        "status": "pending",
    }


@router.get("/permissions")
async def permissions(actor=Depends(require_permission("role.read"))):
    return {
        "domains": PERMISSION_DOMAINS,
        "permissions": PERMISSIONS,
        "count": len(PERMISSIONS),
    }


@router.get("/roles")
async def list_roles(actor=Depends(require_permission("role.read"))):
    return [
        public_document(row)
        async for row in get_db()["roles"].find().sort("priority", 1).limit(100)
    ]


@router.post("/roles", status_code=201)
async def create_role(
    payload: RoleCreate, actor=Depends(require_permission("role.create"))
):
    data = payload.model_dump() | {
        "version": await next_role_version(payload.name),
        "builtin": False,
        "created_at": utcnow(),
    }
    check_target_role(actor, data)
    try:
        async with transaction() as session:
            result = await get_db()["roles"].insert_one(data, session=session)
            await audit(
                "role.create", "roles", result.inserted_id, actor, session=session
            )
    except DuplicateKeyError:
        raise HTTPException(409, "Role name already exists") from None
    await publish_version(role_version_key(data["name"]), data["version"])
    return public_document(data)


@router.patch("/roles/{name}")
async def update_role(
    name: str, payload: RoleUpdate, actor=Depends(require_permission("role.update"))
):
    role = await get_role(name)
    if name == "super_admin":
        raise HTTPException(403, "The super_admin role is immutable")
    check_target_role(actor, role)
    check_target_role(actor, payload.model_dump())
    next_version = role.get("version", 1) + 1
    await publish_version(role_version_key(name), next_version)
    async with transaction() as session:
        result = await get_db()["roles"].update_one(
            {"_id": role["_id"], "version": role.get("version", 1)},
            {
                "$set": payload.model_dump()
                | {"updated_at": utcnow(), "version": next_version}
            },
            session=session,
        )
        if not result.modified_count:
            raise HTTPException(409, "Role changed concurrently; reload and retry")
        await audit(
            "role.update",
            "roles",
            role["_id"],
            actor,
            session=session,
            details={"fields": list(payload.model_fields_set)},
        )
    return public_document(role | payload.model_dump() | {"version": next_version})


@router.delete("/roles/{name}", status_code=204)
async def delete_role(name: str, actor=Depends(require_permission("role.delete"))):
    role = await get_role(name)
    if role.get("builtin"):
        raise HTTPException(403, "Default roles cannot be deleted")
    check_target_role(actor, role)
    async with transaction() as session:
        for realm in ("auth_users", "admin_users"):
            if await get_db()[realm].find_one({"role": name}, session=session):
                raise HTTPException(409, "Role is still assigned to an account")
        await publish_version(role_version_key(name), role.get("version", 1) + 1)
        result = await get_db()["roles"].delete_one(
            {"_id": role["_id"], "version": role.get("version", 1)}, session=session
        )
        if not result.deleted_count:
            raise HTTPException(409, "Role changed concurrently; reload and retry")
        await audit("role.delete", "roles", role["_id"], actor, session=session)


@router.get("/users")
async def list_users(
    realm: Realm = "admin_users",
    limit: int = Query(50, ge=1, le=100),
    actor=Depends(require_permission("user.read")),
):
    return [
        public_user(row, realm)
        async for row in get_db()[realm].find().sort("_id", -1).limit(limit)
    ]


@router.post("/users", status_code=201)
async def create_user(
    payload: UserCreate, actor=Depends(require_permission("user.create"))
):
    role = await get_role(payload.role)
    check_target_role(actor, role)
    # A super-admin can delegate administration, but not mint verified owners.
    doc = {
        "username": payload.username,
        "full_name": payload.full_name,
        "password_hash": await hash_password(payload.password.get_secret_value()),
        "role": payload.role,
        "is_active": True,
        "auth_version": 1,
        "is_verified": False,
        "is_poi_owner_verified": False,
        "created_at": utcnow(),
    }
    try:
        async with transaction() as session:
            await touch_role(role, session)
            result = await get_db()["admin_users"].insert_one(doc, session=session)
            await audit(
                "user.create",
                "admin_users",
                result.inserted_id,
                actor,
                session=session,
                details={"role": payload.role},
            )
    except DuplicateKeyError:
        raise HTTPException(409, "Username already exists") from None
    return public_user(doc, "admin_users")


async def update_account(user_id, payload, realm, actor, *, deleting=False):
    user = await managed_user(actor, realm, user_id)
    changes = payload.model_dump(exclude_none=True, exclude={"password"})
    assigned_role = None
    if "role" in changes:
        assigned_role = await get_role(changes["role"])
        check_target_role(actor, assigned_role)
    if payload.password:
        changes["password_hash"] = await hash_password(
            payload.password.get_secret_value()
        )
    if not changes:
        raise HTTPException(422, "No fields to update")
    version = user.get("auth_version", 1) + 1
    await publish_version(user_version_key(realm, user_id), version)
    changes.update(auth_version=version, updated_at=utcnow())
    if deleting:
        changes.update(
            is_verified=False, is_poi_owner_verified=False, deleted_at=utcnow()
        )
    update = {"$set": changes}
    if deleting:
        update["$unset"] = {"national_id_encrypted": ""}
    async with transaction() as session:
        if assigned_role:
            await touch_role(assigned_role, session)
        result = await get_db()[realm].update_one(
            {"_id": user["_id"], "auth_version": user.get("auth_version", 1)},
            update,
            session=session,
        )
        if not result.modified_count:
            raise HTTPException(409, "Account changed concurrently; reload and retry")
        await audit(
            "user.delete" if deleting else "user.update",
            realm,
            user_id,
            actor,
            session=session,
            details={"fields": sorted(payload.model_fields_set)},
        )
    return public_user(user | changes, realm)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    realm: Realm = "admin_users",
    actor=Depends(require_permission("user.update")),
):
    return await update_account(user_id, payload, realm, actor)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    realm: Realm = "admin_users",
    actor=Depends(require_permission("user.delete")),
):
    await update_account(
        user_id, UserUpdate(is_active=False), realm, actor, deleting=True
    )


@router.get("/registrations")
async def list_registrations(
    status: Literal["pending", "approved", "rejected"] | None = None,
    limit: int = Query(50, ge=1, le=100),
    actor=Depends(require_permission("owner.read")),
):
    query = {"status": status} if status else {}
    return [
        public_document(row)
        async for row in get_db()["poi_owner_registrations"]
        .find(query)
        .sort("_id", -1)
        .limit(limit)
    ]


@router.patch("/registrations/{registration_id}")
async def review_registration(
    registration_id: str,
    payload: ReviewRegistration,
    actor=Depends(require_any_permission("owner.approve", "owner.reject")),
):
    required = "owner.approve" if payload.status == "approved" else "owner.reject"
    if required not in actor["permissions"]:
        raise HTTPException(403, "Permission required: " + required)
    registration = await get_db()["poi_owner_registrations"].find_one(
        {"_id": object_id(registration_id)}
    )
    if not registration:
        raise HTTPException(404, "Registration not found")
    if registration["user_id"] == actor["sub"] and actor["realm"] == "admin_users":
        raise HTTPException(403, "You cannot review your own registration")
    if registration["status"] != "pending":
        raise HTTPException(409, "Registration has already been reviewed")
    user = await get_db()["admin_users"].find_one(
        {"_id": ObjectId(registration["user_id"])}
    )
    if not user or not user.get("is_active") or user.get("role") != "poi_owner":
        raise HTTPException(
            409, "Applicant is inactive or no longer has the owner role"
        )
    version, approved = user.get("auth_version", 1) + 1, payload.status == "approved"
    await publish_version(user_version_key("admin_users", user["_id"]), version)
    changes = {
        "status": payload.status,
        "reason": payload.reason,
        "reviewed_by": actor["sub"],
        "reviewed_at": utcnow(),
    }
    async with transaction() as session:
        updated = await get_db()["poi_owner_registrations"].update_one(
            {"_id": registration["_id"], "status": "pending"},
            {"$set": changes},
            session=session,
        )
        account = await get_db()["admin_users"].update_one(
            {
                "_id": user["_id"],
                "auth_version": user.get("auth_version", 1),
                "is_active": True,
            },
            {
                "$set": {
                    "is_verified": approved,
                    "is_poi_owner_verified": approved,
                    "auth_version": version,
                }
            },
            session=session,
        )
        if not updated.modified_count or not account.modified_count:
            raise HTTPException(
                409, "Registration changed concurrently; reload and retry"
            )
        await audit(
            "owner." + payload.status,
            "poi_owner_registrations",
            registration_id,
            actor,
            session=session,
            details={"status": payload.status},
        )
    return public_document(registration | changes)


@router.post("/owners/{user_id}/suspend")
async def suspend_owner(
    user_id: str, actor=Depends(require_permission("owner.suspend"))
):
    user = await managed_user(actor, "admin_users", user_id)
    if user["role"] != "poi_owner":
        raise HTTPException(409, "Account is not an owner")
    version = user.get("auth_version", 1) + 1
    await publish_version(user_version_key("admin_users", user_id), version)
    async with transaction() as session:
        result = await get_db()["admin_users"].update_one(
            {"_id": user["_id"], "auth_version": user.get("auth_version", 1)},
            {
                "$set": {
                    "is_verified": False,
                    "is_poi_owner_verified": False,
                    "auth_version": version,
                }
            },
            session=session,
        )
        if not result.modified_count:
            raise HTTPException(409, "Account changed concurrently")
        await audit("owner.suspend", "admin_users", user_id, actor, session=session)
    return {"id": user_id, "is_verified": False, "is_poi_owner_verified": False}


@router.get("/registrations/{registration_id}/pii")
async def read_identity(
    registration_id: str,
    response: Response,
    actor=Depends(require_permission("owner.approve")),
    reader=Depends(require_permission("user.read")),
):
    registration = await get_db()["poi_owner_registrations"].find_one(
        {"_id": object_id(registration_id)}
    )
    if not registration:
        raise HTTPException(404, "Registration not found")
    user = await get_db()["admin_users"].find_one(
        {"_id": ObjectId(registration["user_id"])}
    )
    if not user or not pii_is_live(user):
        raise HTTPException(410, "Identity data expired or removed")
    try:
        value = decrypt_pii(user["national_id_encrypted"])
    except (InvalidToken, RuntimeError, ValueError):
        raise HTTPException(
            503, "PII decryption unavailable; check the configured key"
        ) from None
    await audit("pii.read", "admin_users", user["_id"], actor)
    response.headers["Cache-Control"] = "no-store"
    return {"national_id": value, "expires_at": user["pii_expires_at"]}


@router.get("/audit-logs")
async def audit_logs(
    limit: int = Query(50, ge=1, le=100),
    before: str | None = None,
    actor=Depends(require_permission("audit.read")),
):
    query = {"_id": {"$lt": object_id(before)}} if before else {}
    rows = [
        public_document(row)
        async for row in get_db()["audit_logs"].find(query).sort("_id", -1).limit(limit)
    ]
    return {
        "items": rows,
        "next_before": rows[-1]["id"] if len(rows) == limit else None,
    }
