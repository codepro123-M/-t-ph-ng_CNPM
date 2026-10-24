"""Idempotent indexes, role seeds, and explicit super-admin bootstrap."""

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.auth.schemas import Registration
from app.core.audit import audit, transaction
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import DEFAULT_ROLES
from app.core.security import hash_password, utcnow
from app.core.sessions import publish_version, role_version_key


async def ensure_auth_indexes():
    db = get_db()
    for name in ("auth_users", "admin_users"):
        await db[name].create_index(
            "username",
            unique=True,
            name="auth_username_unique"
            if name == "auth_users"
            else "admin_username_unique",
        )
        await db[name].update_many(
            {"auth_version": {"$exists": False}}, {"$set": {"auth_version": 1}}
        )
    await db["roles"].create_index("name", unique=True, name="unique_role_name")
    await db["refresh_sessions"].create_index(
        "expires_at", expireAfterSeconds=0, name="expired_sessions"
    )
    await db["refresh_sessions"].create_index([("realm", 1), ("user_id", 1)])
    await db["poi_owner_registrations"].create_index("user_id", unique=True)
    await db["poi_owner_registrations"].create_index(
        [("status", 1), ("created_at", -1)]
    )
    await db["admin_users"].create_index("pii_expires_at")  # deliberately NOT TTL
    await db["audit_logs"].create_index([("created_at", -1), ("_id", -1)])
    for name in ("owner_rooms", "owner_posts"):
        await db[name].create_index([("owner_id", 1), ("created_at", -1)])


async def ensure_roles():
    db = get_db()
    for name, values in DEFAULT_ROLES.items():
        try:
            async with transaction() as session:
                result = await db["roles"].update_one(
                    {"name": name},
                    {
                        "$setOnInsert": values
                        | {
                            "name": name,
                            "version": 1,
                            "builtin": True,
                            "booking_permissions_version": 1,
                            "created_at": utcnow(),
                        }
                    },
                    upsert=True,
                    session=session,
                )
                if result.upserted_id:
                    await audit(
                        "role.seed", "roles", result.upserted_id, session=session
                    )
        except DuplicateKeyError:
            result = None
        role = await db["roles"].find_one({"name": name})
        # Add only the new booking grants to the built-in administrator roles.
        # Custom roles and all other administrator changes remain untouched.
        if (
            name in {"super_admin", "admin"}
            and role.get("builtin")
            and not role.get("booking_permissions_version")
        ):
            missing = {"booking.read", "booking.update"} - set(role["permissions"])
            async with transaction() as session:
                changes = {"$set": {"booking_permissions_version": 1}}
                if missing:
                    changes.update(
                        {
                            "$addToSet": {"permissions": {"$each": sorted(missing)}},
                            "$inc": {"version": 1},
                        }
                    )
                changed = await db["roles"].update_one(
                    {
                        "_id": role["_id"],
                        "version": role.get("version", 1),
                        "booking_permissions_version": {"$exists": False},
                    },
                    changes,
                    session=session,
                )
                if changed.modified_count:
                    await audit(
                        "role.booking_migration", "roles", role["_id"], session=session
                    )
            role = await db["roles"].find_one({"name": name})
        await publish_version(role_version_key(name), role.get("version", 1))


async def ensure_super_admin():
    mode = settings.SUPERADMIN_BOOTSTRAP_MODE
    if mode == "disabled":
        return
    db = get_db()
    existing = await db["admin_users"].find_one(
        {"role": "super_admin", "is_active": True}
    )
    if mode == "auto" and existing:
        return
    if not settings.SUPERADMIN_USERNAME or not settings.SUPERADMIN_PASSWORD:
        raise RuntimeError(
            "Super-admin bootstrap needs SUPERADMIN_USERNAME and SUPERADMIN_PASSWORD. Run configure_phase2.py, or use mode=disabled."
        )
    try:
        supplied = Registration(
            username=settings.SUPERADMIN_USERNAME,
            password=settings.SUPERADMIN_PASSWORD,
            full_name="Super Administrator",
        )
    except ValueError:
        raise RuntimeError(
            "Invalid super-admin credentials; use a valid username and an 8-72 byte password."
        ) from None
    same_user = await db["admin_users"].find_one({"username": supplied.username})
    if same_user:
        if same_user.get("role") != "super_admin" or not same_user.get("is_active"):
            raise RuntimeError(
                "Bootstrap username belongs to another or disabled account. No promotion was performed."
            )
        return
    if existing:
        raise RuntimeError(
            "An active super-admin already exists under another username."
        )
    user_id = ObjectId()
    password_hash = await hash_password(supplied.password.get_secret_value())
    try:
        async with transaction() as session:
            await db["bootstrap_markers"].insert_one(
                {"_id": "super_admin", "created_at": utcnow()}, session=session
            )
            await db["admin_users"].insert_one(
                {
                    "_id": user_id,
                    "username": supplied.username,
                    "full_name": supplied.full_name,
                    "password_hash": password_hash,
                    "role": "super_admin",
                    "auth_version": 1,
                    "is_active": True,
                    "is_verified": True,
                    "is_poi_owner_verified": False,
                    "created_at": utcnow(),
                },
                session=session,
            )
            await audit("user.bootstrap", "admin_users", user_id, session=session)
    except DuplicateKeyError:
        account = await db["admin_users"].find_one(
            {"role": "super_admin", "is_active": True}
        )
        if not account:
            raise RuntimeError(
                "Bootstrap marker exists without an active super-admin; restore or repair the account explicitly."
            ) from None
