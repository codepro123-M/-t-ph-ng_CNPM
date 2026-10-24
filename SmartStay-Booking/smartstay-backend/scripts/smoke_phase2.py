"""Integration smoke against a running stack (creates random test accounts).

Run locally: python scripts/smoke_phase2.py
Credentials are read from .env, never printed. Owner/account test rows remain.
"""

import argparse
import secrets
from pathlib import Path

import httpx

from configure_phase2 import read_values


def expect(response, code):
    if response.status_code != code:
        raise AssertionError(
            f"{response.request.method} {response.request.url.path}: expected {code}, got {response.status_code}"
        )
    return response.json() if code not in {204, 304} else None


def run(base_url, username, password, *, verify=True):
    suffix = secrets.token_hex(5)
    owner_name, owner_password = "owner_" + suffix, secrets.token_urlsafe(20)
    payload = {
        "username": owner_name,
        "password": owner_password,
        "full_name": "Phase 2 test owner",
        "email": f"{suffix}@example.com",
        "phone": "+84912345678",
        "property_name": "Phase 2 test stay",
        "property_address": "Integration test",
        "national_id": "000000000001",
    }
    with httpx.Client(
        base_url=base_url, verify=verify, timeout=30, trust_env=False
    ) as client:
        root = expect(
            client.post(
                "/admin/auth/login",
                json={"username": username, "password": password, "mode": "bearer"},
            ),
            200,
        )
        headers = {"Authorization": "Bearer " + root["access_token"]}
        catalog = expect(client.get("/admin/permissions", headers=headers), 200)
        assert catalog["count"] == 34 and len(catalog["domains"]) == 10
        roles = expect(client.get("/admin/roles", headers=headers), 200)
        assert {row["name"] for row in roles}.issuperset(
            {"super_admin", "admin", "poi_owner", "user"}
        )
        registration = expect(
            client.post("/admin/auth/register-owner", json=payload), 201
        )
        owner = expect(
            client.post(
                "/admin/auth/login",
                json={
                    "username": owner_name,
                    "password": owner_password,
                    "mode": "bearer",
                },
            ),
            200,
        )
        owner_header = {"Authorization": "Bearer " + owner["access_token"]}
        expect(client.get("/owner/rooms", headers=owner_header), 403)
        expect(
            client.patch(
                "/admin/registrations/" + registration["registration_id"],
                json={"status": "approved"},
                headers=headers,
            ),
            200,
        )
        expect(client.get("/owner/rooms", headers=owner_header), 401)
        rotated = expect(
            client.post(
                "/admin/auth/refresh", json={"refresh_token": owner["refresh_token"]}
            ),
            200,
        )
        owner_header = {"Authorization": "Bearer " + rotated["access_token"]}
        assert (
            rotated["user"]["is_verified"] and rotated["user"]["is_poi_owner_verified"]
        )
        room = expect(
            client.post(
                "/owner/rooms",
                json={"name": "Test room", "price": 100000},
                headers=owner_header,
            ),
            201,
        )
        expect(
            client.patch(
                "/owner/rooms/" + room["id"],
                json={"name": "Updated room", "price": 120000},
                headers=owner_header,
            ),
            200,
        )
        post = expect(
            client.post(
                "/owner/posts",
                json={"title": "Test post", "body": "Integration content"},
                headers=owner_header,
            ),
            201,
        )
        expect(
            client.post("/owner/posts/" + post["id"] + "/submit", headers=owner_header),
            200,
        )
        expect(client.delete("/owner/rooms/" + room["id"], headers=owner_header), 204)
        expect(client.delete("/owner/posts/" + post["id"], headers=owner_header), 204)
        expect(
            client.post(
                "/admin/auth/refresh", json={"refresh_token": owner["refresh_token"]}
            ),
            401,
        )
        expect(client.get("/owner/rooms", headers=owner_header), 401)
        logs = expect(client.get("/admin/audit-logs", headers=headers), 200)["items"]
        assert any(row["action"] == "owner.approved" for row in logs)
        assert payload["national_id"] not in str(logs)
        assert owner_password not in str(logs)
        expect(
            client.delete(
                "/admin/users/" + registration["user"]["id"], headers=headers
            ),
            204,
        )
    print(
        "PASS: 34 permissions, roles, owner registration, approval, revocation, refresh rotation, room/post CRUD, audit, deactivation"
    )


def run_cookie(base_url, username, password, *, verify=True):
    with httpx.Client(
        base_url=base_url, verify=verify, timeout=30, trust_env=False
    ) as client:
        response = client.post(
            "/admin/auth/login", json={"username": username, "password": password}
        )
        result = expect(response, 200)
        assert "access_token" not in result and "refresh_token" not in result
        assert all(
            "Secure" in cookie and "SameSite=lax" in cookie
            for cookie in response.headers.get_list("set-cookie")
        )
        expect(client.get("/admin/roles"), 200)
        expect(client.post("/admin/auth/refresh"), 403)
        csrf = client.cookies["csrf_token"]
        expect(client.post("/admin/auth/refresh", headers={"X-CSRF-Token": csrf}), 200)
        expect(client.post("/admin/auth/logout", headers={"X-CSRF-Token": csrf}), 204)
        expect(client.get("/admin/roles"), 401)
    print("PASS: HTTPS Secure/HttpOnly cookies, CSRF check, cookie refresh and logout")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--cookie-url", default="")
    parser.add_argument("--ca-file", default="")
    args = parser.parse_args()
    values = read_values(
        (Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8-sig")
    )
    username, password = (
        values.get("SUPERADMIN_USERNAME", ""),
        values.get("SUPERADMIN_PASSWORD", ""),
    )
    if not username or not password:
        raise SystemExit("Configure bootstrap credentials in .env first")
    try:
        run(args.base_url, username, password, verify=args.ca_file or True)
        if args.cookie_url:
            run_cookie(args.cookie_url, username, password, verify=args.ca_file or True)
    except (httpx.HTTPError, AssertionError) as exc:
        raise SystemExit(f"Phase 2 smoke failed: {exc}") from None


if __name__ == "__main__":
    main()
