import json
from datetime import timedelta
from unittest.mock import AsyncMock

import bcrypt
import jwt
import pytest
from bson import ObjectId
from redis.exceptions import ConnectionError

from app.admin.bootstrap import ensure_roles, ensure_super_admin
from app.core.config import settings
from app.core.database import db_manager
from app.core.permissions import PERMISSION_DOMAINS, PERMISSIONS
from app.core.pii import decrypt_pii, encrypt_pii
from app.core.retention import purge_expired_pii
from app.core.security import utcnow
from test_auth import login, register

ROOT_PASSWORD = "Root-test-password-2026"
OWNER = {
    "username": "owner_minh",
    "password": "Owner-pass-2026",
    "full_name": "Minh Owner",
    "email": "minh@example.com",
    "phone": "+84912345678",
    "property_name": "Minh Stay",
    "property_address": "Da Nang",
    "national_id": "012345678901",
}
ROOM = {"name": "Phòng đôi", "price": 500000, "max_guests": 2}


def auth(token):
    return {"Authorization": "Bearer " + token}


def admin_login(client, username="superadmin", password=ROOT_PASSWORD, mode="bearer"):
    response = client.post(
        "/admin/auth/login",
        json={"username": username, "password": password, "mode": mode},
    )
    assert response.status_code == 200, response.text
    return response.json()


def new_owner(client, username=None):
    response = client.post(
        "/admin/auth/register-owner",
        json=OWNER | ({"username": username} if username else {}),
    )
    assert response.status_code == 201, response.text
    return response.json()


def approve(client, root, registration):
    response = client.patch(
        "/admin/registrations/" + registration["registration_id"],
        json={"status": "approved"},
        headers=auth(root),
    )
    assert response.status_code == 200, response.text


def verified_owner(client, root):
    registration = new_owner(client)
    approve(client, root, registration)
    return admin_login(client, OWNER["username"], OWNER["password"]), registration


def test_catalog_and_idempotent_roles(client, services):
    assert len(PERMISSIONS) == len(set(PERMISSIONS)) == 34
    assert len(PERMISSION_DOMAINS) == 10
    assert {r["name"]: r["priority"] for r in services.db.raw.roles.find()} == {
        "super_admin": 0,
        "admin": 1,
        "poi_owner": 10,
        "user": 100,
    }
    services.db.raw.roles.update_one(
        {"name": "admin"}, {"$set": {"permissions": ["poi.read"], "version": 2}}
    )
    client.portal.call(ensure_roles)
    assert services.db.raw.roles.find_one({"name": "admin"})["permissions"] == [
        "poi.read"
    ]
    assert services.db.raw.roles.count_documents({}) == 4


def test_owner_registration_encryption_and_pending_gate(client, services):
    created = new_owner(client)
    user = services.db.raw.admin_users.find_one(
        {"_id": ObjectId(created["user"]["id"])}
    )
    assert user["national_id_encrypted"].startswith("v1:")
    assert decrypt_pii(user["national_id_encrypted"]) == OWNER["national_id"]
    assert (user["pii_expires_at"] - user["created_at"]).days == 180
    assert not user["is_verified"] and not user["is_poi_owner_verified"]
    row = services.db.raw.poi_owner_registrations.find_one()
    assert row["status"] == "pending" and "national_id_encrypted" not in row
    assert OWNER["national_id"] not in json.dumps(created)
    token = admin_login(client, OWNER["username"], OWNER["password"])["access_token"]
    assert client.get("/owner/rooms", headers=auth(token)).status_code == 403
    assert (
        client.post(
            "/owner/posts", json={"title": "Test", "body": "Body"}, headers=auth(token)
        ).status_code
        == 403
    )
    assert (
        client.get("/owner/profile", headers=auth(token)).json()["registration"][
            "status"
        ]
        == "pending"
    )
    logs = json.dumps(list(services.db.raw.audit_logs.find()), default=str)
    assert OWNER["national_id"] not in logs and OWNER["password"] not in logs
    assert user["national_id_encrypted"] not in logs


@pytest.mark.parametrize(
    "field,value",
    [("role", "super_admin"), ("is_verified", True), ("is_poi_owner_verified", True)],
)
def test_public_owner_cannot_set_privilege_fields(client, field, value):
    response = client.post("/admin/auth/register-owner", json=OWNER | {field: value})
    assert response.status_code == 422
    assert OWNER["national_id"] not in response.text
    assert OWNER["password"] not in response.text


def test_approval_flags_refresh_owner_crud_and_audit(client, services, root):
    registration = new_owner(client)
    old = admin_login(client, OWNER["username"], OWNER["password"])
    approve(client, root, registration)
    stored = services.db.raw.admin_users.find_one({"username": OWNER["username"]})
    assert stored["is_verified"] and stored["is_poi_owner_verified"]
    assert (
        client.get("/owner/rooms", headers=auth(old["access_token"])).status_code == 401
    )
    rotated = client.post(
        "/admin/auth/refresh", json={"refresh_token": old["refresh_token"]}
    )
    assert rotated.status_code == 200, rotated.text
    token = rotated.json()["access_token"]
    created = client.post("/owner/rooms", json=ROOM, headers=auth(token))
    assert created.status_code == 201, created.text
    room_id = created.json()["id"]
    assert (
        client.patch(
            "/owner/rooms/" + room_id,
            json=ROOM | {"price": 600000},
            headers=auth(token),
        ).status_code
        == 200
    )
    assert len(client.get("/owner/rooms", headers=auth(token)).json()) == 1
    post = client.post(
        "/owner/posts",
        json={"title": "Bài viết", "body": "Nội dung"},
        headers=auth(token),
    )
    assert post.status_code == 201
    post_id = post.json()["id"]
    assert (
        client.post(f"/owner/posts/{post_id}/submit", headers=auth(token)).json()[
            "status"
        ]
        == "pending"
    )
    assert (
        client.post(f"/owner/posts/{post_id}/submit", headers=auth(token)).status_code
        == 409
    )
    assert (
        client.delete("/owner/rooms/" + room_id, headers=auth(token)).status_code == 204
    )
    actions = {row["action"] for row in services.db.raw.audit_logs.find()}
    assert {"owner.approved", "create", "update", "submit", "delete"}.issubset(actions)


def test_owner_isolation(client, root):
    first, _ = verified_owner(client, root)
    room = client.post(
        "/owner/rooms", json=ROOM, headers=auth(first["access_token"])
    ).json()
    second_reg = new_owner(client, "another_owner")
    approve(client, root, second_reg)
    second = admin_login(client, "another_owner", OWNER["password"])["access_token"]
    for method, kwargs in [("get", {}), ("patch", {"json": ROOM}), ("delete", {})]:
        response = getattr(client, method)(
            "/owner/rooms/" + room["id"], headers=auth(second), **kwargs
        )
        assert response.status_code == 404
    assert client.get("/owner/rooms", headers=auth(second)).json() == []


def test_suspension_and_deactivation_revoke_old_tokens(client, root):
    owner, registration = verified_owner(client, root)
    user_id = registration["user"]["id"]
    assert (
        client.post(f"/admin/owners/{user_id}/suspend", headers=auth(root)).status_code
        == 200
    )
    assert (
        client.get("/owner/rooms", headers=auth(owner["access_token"])).status_code
        == 401
    )
    refreshed = client.post(
        "/admin/auth/refresh", json={"refresh_token": owner["refresh_token"]}
    ).json()
    assert (
        client.get("/owner/rooms", headers=auth(refreshed["access_token"])).status_code
        == 403
    )
    assert (
        client.patch(
            f"/admin/users/{user_id}", json={"is_active": False}, headers=auth(root)
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/auth/me", headers=auth(refreshed["access_token"])
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/admin/auth/refresh", json={"refresh_token": refreshed["refresh_token"]}
        ).status_code
        == 401
    )


def test_cookie_flags_csrf_and_bearer_priority(client, services, root):
    result = admin_login(client, mode="cookie")
    assert "access_token" not in result and "refresh_token" not in result
    assert all(
        name in client.cookies
        for name in ("access_token", "refresh_token", "csrf_token")
    )
    response = client.post(
        "/admin/auth/login", json={"username": "superadmin", "password": ROOT_PASSWORD}
    )
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 3
    assert all("Secure" in cookie and "SameSite=lax" in cookie for cookie in cookies)
    assert all(
        "HttpOnly" in cookie
        for cookie in cookies
        if not cookie.startswith("csrf_token=")
    )
    assert client.get("/admin/roles").status_code == 200
    assert (
        client.get(
            "/admin/roles", headers={"Authorization": "Bearer broken"}
        ).status_code
        == 401
    )
    assert client.post("/admin/auth/refresh").status_code == 403
    csrf = client.cookies["csrf_token"]
    assert (
        client.post(
            "/admin/auth/refresh",
            headers={"X-CSRF-Token": csrf, "Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/admin/auth/refresh",
            headers={"X-CSRF-Token": csrf, "Origin": "https://localhost:8443"},
        ).status_code
        == 200
    )
    assert (
        client.post("/admin/auth/logout", headers={"X-CSRF-Token": csrf}).status_code
        == 204
    )
    assert (
        "access_token" not in client.cookies and "refresh_token" not in client.cookies
    )
    assert client.get("/admin/roles").status_code == 401


def test_cookie_login_rejects_http_and_hostile_origin(client, root):
    credentials = {"username": "superadmin", "password": ROOT_PASSWORD}
    assert (
        client.post(
            "http://localhost:8001/admin/auth/login", json=credentials
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/admin/auth/login",
            json=credentials,
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )


def test_refresh_rotation_reuse_and_logout(client):
    register(client)
    original = login(client).json()
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )
    assert response.status_code == 200, response.text
    new = response.json()
    assert new["refresh_token"] != original["refresh_token"]
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get("/api/v1/auth/me", headers=auth(new["access_token"])).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}
        ).status_code
        == 401
    )
    another = login(client).json()
    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": another["refresh_token"]}
        ).status_code
        == 204
    )
    assert (
        client.get("/api/v1/auth/me", headers=auth(another["access_token"])).status_code
        == 401
    )


def test_guards_no_mongo_queries_and_redis_fail_closed(client, services, monkeypatch):
    register(client)
    token = login(client).json()["access_token"]
    monkeypatch.setattr(db_manager, "db", None)
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200
    monkeypatch.setattr(
        services.redis, "get", AsyncMock(side_effect=ConnectionError("down"))
    )
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 503


def test_role_change_invalidates_tokens_and_does_not_allow_escalation(client, root):
    headers = auth(root)
    role = {"name": "reviewer", "priority": 20, "permissions": ["owner.read"]}
    assert client.post("/admin/roles", json=role, headers=headers).status_code == 201
    person = client.post(
        "/admin/users",
        json={
            "username": "reviewer1",
            "full_name": "Reviewer",
            "password": "Reviewer-pass2026",
            "role": "reviewer",
        },
        headers=headers,
    )
    assert person.status_code == 201
    tokens = admin_login(client, "reviewer1", "Reviewer-pass2026")
    assert (
        client.get(
            "/admin/registrations", headers=auth(tokens["access_token"])
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/admin/roles",
            json=role | {"name": "evil"},
            headers=auth(tokens["access_token"]),
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/admin/roles/reviewer",
            json={"priority": 20, "permissions": []},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/admin/registrations", headers=auth(tokens["access_token"])
        ).status_code
        == 401
    )
    new = client.post(
        "/admin/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert new.status_code == 200
    assert (
        client.get(
            "/admin/registrations", headers=auth(new.json()["access_token"])
        ).status_code
        == 403
    )
    assert client.delete("/admin/roles/reviewer", headers=headers).status_code == 409
    assert (
        client.patch(
            "/admin/roles/super_admin",
            json={"priority": 1, "permissions": []},
            headers=headers,
        ).status_code
        == 403
    )


def test_admin_cannot_grant_higher_or_unowned_permissions(client, root):
    created = client.post(
        "/admin/users",
        json={
            "username": "admin1",
            "full_name": "Admin",
            "password": "Admin-pass2026",
            "role": "admin",
        },
        headers=auth(root),
    )
    assert created.status_code == 201
    token = admin_login(client, "admin1", "Admin-pass2026")["access_token"]
    assert (
        client.post(
            "/admin/users",
            json={
                "username": "root2",
                "full_name": "Root2",
                "password": "Root-pass2026",
                "role": "super_admin",
            },
            headers=auth(token),
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/admin/roles",
            json={"name": "escalator", "priority": 2, "permissions": ["system.update"]},
            headers=auth(token),
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/admin/roles/admin",
            json={"priority": 2, "permissions": []},
            headers=auth(token),
        ).status_code
        == 403
    )


def test_pii_expiry_hides_then_purges_ciphertext_without_deleting_account(
    client, services, root
):
    registration = new_owner(client)
    path = "/admin/registrations/" + registration["registration_id"] + "/pii"
    live = client.get(path, headers=auth(root))
    assert (
        live.status_code == 200 and live.json()["national_id"] == OWNER["national_id"]
    )
    assert live.headers["cache-control"] == "no-store"
    services.db.raw.admin_users.update_one(
        {"username": OWNER["username"]},
        {"$set": {"pii_expires_at": utcnow() - timedelta(seconds=1)}},
    )
    assert client.get(path, headers=auth(root)).status_code == 410
    assert client.portal.call(purge_expired_pii) == 1
    account = services.db.raw.admin_users.find_one({"username": OWNER["username"]})
    assert account is not None and "national_id_encrypted" not in account
    assert client.portal.call(purge_expired_pii) == 0
    assert services.db.raw.audit_logs.count_documents({"action": "pii.purge"}) == 1
    assert all(
        "expireAfterSeconds" not in index
        for index in services.db.raw.admin_users.index_information().values()
    )


def test_audit_failure_rolls_back_owner_and_registration(client, services, monkeypatch):
    import app.admin.router as module

    monkeypatch.setattr(
        module, "audit", AsyncMock(side_effect=RuntimeError("audit unavailable"))
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        new_owner(client)
    assert (
        services.db.raw.admin_users.count_documents({"username": OWNER["username"]})
        == 0
    )
    assert services.db.raw.poi_owner_registrations.count_documents({}) == 0


def test_audit_failure_rolls_back_room(client, services, root, monkeypatch):
    tokens, _ = verified_owner(client, root)
    import app.owner.router as module

    monkeypatch.setattr(
        module, "audit", AsyncMock(side_effect=RuntimeError("audit unavailable"))
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.post("/owner/rooms", json=ROOM, headers=auth(tokens["access_token"]))
    assert services.db.raw.owner_rooms.count_documents({}) == 0


def test_superadmin_bootstrap_idempotence_and_no_password_reset(
    client, services, monkeypatch
):
    monkeypatch.setattr(settings, "SUPERADMIN_BOOTSTRAP_MODE", "env_only")
    monkeypatch.setattr(settings, "SUPERADMIN_USERNAME", "bootstrap_root")
    monkeypatch.setattr(settings, "SUPERADMIN_PASSWORD", ROOT_PASSWORD)
    client.portal.call(ensure_super_admin)
    stored = services.db.raw.admin_users.find_one({"username": "bootstrap_root"})
    monkeypatch.setattr(settings, "SUPERADMIN_PASSWORD", "A-different-new-password")
    client.portal.call(ensure_super_admin)
    assert services.db.raw.admin_users.count_documents({"role": "super_admin"}) == 1
    assert (
        services.db.raw.admin_users.find_one({"_id": stored["_id"]})["password_hash"]
        == stored["password_hash"]
    )
    assert (
        admin_login(client, "bootstrap_root", ROOT_PASSWORD)["user"]["role"]
        == "super_admin"
    )


def test_bootstrap_rejects_missing_credentials(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPERADMIN_BOOTSTRAP_MODE", "env_only")
    monkeypatch.setattr(settings, "SUPERADMIN_USERNAME", "")
    monkeypatch.setattr(settings, "SUPERADMIN_PASSWORD", "")
    with pytest.raises(RuntimeError, match="bootstrap needs"):
        client.portal.call(ensure_super_admin)


def test_no_public_secret_key_for_pii(client, monkeypatch):
    monkeypatch.setattr(
        settings, "SECRET_KEY", "dev-fernet-and-app-secret-key-change-in-prod"
    )
    with pytest.raises(RuntimeError, match="strong SECRET_KEY"):
        encrypt_pii(OWNER["national_id"])
    assert client.post("/admin/auth/register-owner", json=OWNER).status_code == 503


def test_access_and_refresh_keys_are_not_interchangeable(client):
    register(client)
    tokens = login(client).json()
    assert (
        client.get("/api/v1/auth/me", headers=auth(tokens["refresh_token"])).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
        ).status_code
        == 401
    )
    claims = jwt.decode(
        tokens["access_token"],
        settings.JWT_SECRET,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
    )
    forged = jwt.encode(claims, "wrong-signing-key", algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers=auth(forged)).status_code == 401


def test_deleted_role_name_can_be_reused_with_new_epoch(client, root):
    headers = auth(root)
    role = {"name": "temporary_role", "priority": 20, "permissions": ["owner.read"]}
    first = client.post("/admin/roles", json=role, headers=headers)
    assert first.status_code == 201
    assert (
        client.delete("/admin/roles/temporary_role", headers=headers).status_code == 204
    )
    second = client.post("/admin/roles", json=role, headers=headers)
    assert second.status_code == 201
    assert second.json()["version"] > first.json()["version"]
    user = client.post(
        "/admin/users",
        json={
            "username": "temporary_user",
            "full_name": "Temp",
            "password": "Temp-user-pass2026",
            "role": "temporary_role",
        },
        headers=headers,
    )
    assert user.status_code == 201
    assert (
        admin_login(client, "temporary_user", "Temp-user-pass2026")["user"]["role"]
        == "temporary_role"
    )


def test_legacy_user_index_and_version_migration(services):
    from fastapi.testclient import TestClient
    from app import main

    password_hash = bcrypt.hashpw(b"Legacy-pass2026", bcrypt.gensalt()).decode()
    services.users.create_index("username", unique=True, name="auth_username_unique")
    services.users.insert_one(
        {
            "username": "legacy",
            "full_name": "Legacy User",
            "password_hash": password_hash,
            "is_active": True,
            "role": "user",
        }
    )
    with TestClient(main.create_app()) as client:
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "legacy", "password": "Legacy-pass2026"},
        )
        assert response.status_code == 200
        assert services.users.find_one({"username": "legacy"})["auth_version"] == 1


def test_role_and_any_permission_guards(client, root):
    from fastapi import Depends
    from app.core.rbac import require_any_permission, require_role

    @client.app.get("/guard-role")
    async def role_guard(actor=Depends(require_role("super_admin"))):
        return {"ok": True}

    @client.app.get("/guard-any")
    async def any_guard(
        actor=Depends(require_any_permission("audit.read", "system.read")),
    ):
        return {"ok": True}

    assert client.get("/guard-role", headers=auth(root)).status_code == 200
    assert client.get("/guard-any", headers=auth(root)).status_code == 200
    register(client)
    token = login(client).json()["access_token"]
    assert client.get("/guard-role", headers=auth(token)).status_code == 403
    assert client.get("/guard-any", headers=auth(token)).status_code == 403


def test_rejected_registration_remains_unverified_and_cannot_be_reviewed_twice(
    client, services, root
):
    registration = new_owner(client)
    path = "/admin/registrations/" + registration["registration_id"]
    assert (
        client.patch(
            path,
            json={"status": "rejected", "reason": "Missing verification"},
            headers=auth(root),
        ).status_code
        == 200
    )
    account = services.db.raw.admin_users.find_one({"username": OWNER["username"]})
    assert not account["is_verified"] and not account["is_poi_owner_verified"]
    assert (
        client.patch(path, json={"status": "approved"}, headers=auth(root)).status_code
        == 409
    )


def test_redis_state_loss_rejects_existing_sessions(client, services):
    register(client)
    token = login(client).json()["access_token"]
    client.portal.call(services.redis.flushall)
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401
    assert login(client).status_code == 200
