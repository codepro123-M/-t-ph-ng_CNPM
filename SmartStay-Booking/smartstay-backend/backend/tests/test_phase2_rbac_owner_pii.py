"""Legacy import/URL regression checks run through the canonical real-storage API."""

import pytest

from app.core.permissions import (
    ALL_PERMISSIONS,
    DEFAULT_ROLES,
    PERMISSIONS,
    PERMISSION_DOMAINS,
    PERMISSIONS_BY_DOMAIN,
)
from app.core.pii import decrypt_pii, encrypt_pii
from app.core.security import hash_password, verify_password
from test_phase2 import ROOT_PASSWORD, auth


def test_permission_import_aliases_share_one_catalog(client, root):
    assert (
        ALL_PERMISSIONS is PERMISSIONS and PERMISSIONS_BY_DOMAIN is PERMISSION_DOMAINS
    )
    assert len(PERMISSIONS) == 34 and len(PERMISSION_DOMAINS) == 10
    assert "booking.read" in DEFAULT_ROLES["super_admin"]["permissions"]
    assert (
        client.get("/api/v1/admin/rbac/permissions", headers=auth(root)).json()["count"]
        == 34
    )


@pytest.mark.asyncio
async def test_shared_password_and_versioned_pii_helpers(client):
    password_hash = await hash_password("Password-regression-2026")
    assert await verify_password("Password-regression-2026", password_hash)
    assert not await verify_password("wrong", password_hash)
    encrypted = encrypt_pii("000000000001")
    assert encrypted.startswith("v1:") and decrypt_pii(encrypted) == "000000000001"


def test_admin_url_alias_uses_username_sessions(client, root):
    login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "superadmin", "password": ROOT_PASSWORD, "mode": "bearer"},
    )
    assert login.status_code == 200
    assert (
        client.get(
            "/api/v1/admin/auth/me", headers=auth(login.json()["access_token"])
        ).json()["realm"]
        == "admin_users"
    )
    assert (
        client.post(
            "/api/v1/admin/auth/login",
            json={"email": "superadmin@smartstay.vn", "password": "unused"},
        ).status_code
        == 422
    )
