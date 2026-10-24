"""Regression for legacy URLs against the transactional application services."""

from datetime import timedelta

from bson import ObjectId

from app.core.security import utcnow
from test_phase2 import OWNER, admin_login, auth, new_owner, verified_owner


def test_dynamic_rbac_32_permissions_and_9_domains(client, root):
    endpoint = "/api/v1/admin/rbac/permissions"
    assert client.get(endpoint).status_code == 401
    catalog = client.get(endpoint, headers=auth(root))
    assert catalog.status_code == 200
    assert catalog.json()["count"] == 34 and len(catalog.json()["domains"]) == 10
    registration = new_owner(client)
    owner = admin_login(client, OWNER["username"], OWNER["password"])
    assert registration["status"] == "pending"
    assert client.get(endpoint, headers=auth(owner["access_token"])).status_code == 403


def test_bcrypt_and_fernet_v1_pii_encryption(client, root, services):
    registration = new_owner(client)
    user_id = ObjectId(registration["user"]["id"])
    stored = services.db.raw.admin_users.find_one({"_id": user_id})
    assert stored["password_hash"].startswith("$2")
    assert stored["national_id_encrypted"].startswith("v1:")
    assert OWNER["national_id"] not in str(list(services.db.raw.audit_logs.find()))
    services.db.raw.admin_users.update_one(
        {"_id": user_id}, {"$set": {"pii_expires_at": utcnow() - timedelta(seconds=1)}}
    )
    response = client.get(
        f"/api/v1/admin/registrations/{registration['registration_id']}/pii",
        headers=auth(root),
    )
    assert response.status_code == 410


def test_end_to_end_owner_registration_verification_and_audit_logs(client, root):
    tokens, registration = verified_owner(client, root)
    owner_header = auth(tokens["access_token"])
    profile = client.get("/api/v1/owner/profile", headers=owner_header)
    assert profile.status_code == 200
    assert profile.json()["id"] == registration["user"]["id"]
    assert profile.json()["is_verified"] and profile.json()["is_poi_owner_verified"]
    assert client.get("/api/v1/admin/me", headers=auth(root)).status_code == 200
    room = client.post(
        "/api/v1/owner/rooms",
        json={"name": "Legacy route room", "price": 500000},
        headers=owner_header,
    )
    assert room.status_code == 201
    audit = client.get("/api/v1/admin/audit-logs", headers=auth(root))
    assert audit.status_code == 200
    assert any(row["resource_id"] == room.json()["id"] for row in audit.json()["items"])
