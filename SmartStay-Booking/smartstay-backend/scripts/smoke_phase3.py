"""Check Phase 3 against a running development stack; only its own test rows are changed."""

import argparse
import secrets
import struct
import zlib
from pathlib import Path

import httpx

from configure_phase2 import read_values
from smoke_phase2 import expect


def tiny_png():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x00\x40\xff" * 4) * 4))
        + chunk(b"IEND", b"")
    )


def header(tokens):
    return {"Authorization": "Bearer " + tokens["access_token"]}


def login(client, username, password):
    return expect(
        client.post(
            "/admin/auth/login",
            json={"username": username, "password": password, "mode": "bearer"},
        ),
        200,
    )


def full_sync(client, language="fr", cursor=None):
    all_items, removed = [], []
    params = {"language": language, "limit": 100}
    if cursor:
        params["cursor"] = cursor
    for _ in range(1000):
        response = client.get("/poi/load-all", params=params)
        page = expect(response, 200)
        all_items.extend(page["items"])
        removed.extend(page["removed_poi_ids"])
        if not page["has_more"]:
            return {
                "items": all_items,
                "removed_poi_ids": removed,
                "sync_cursor": page["sync_cursor"],
                "as_of": page["as_of"],
            }
        params = {"cursor": page["sync_cursor"]}
    raise AssertionError("Sync did not finish within 1000 pages")


def run(base_url, username, password, *, verify=True):
    suffix = secrets.token_hex(5)
    owner_name, owner_password = "content_" + suffix, secrets.token_urlsafe(24)
    source = {
        "name": "Homestay smoke " + suffix,
        "description": "Noi dung luu tru kiem thu",
        "check_in_instructions": "Nhan phong tu 14 gio",
        "category": "homestay",
        "address": "Da Nang",
        "latitude": 16.0544,
        "longitude": 108.2022,
    }
    created_accounts, poi_id = [], None
    with httpx.Client(
        base_url=base_url.rstrip("/"), timeout=30, trust_env=False, verify=verify
    ) as client:
        readiness = expect(client.get("/health/ready"), 200)
        assert all(
            readiness.get(name) is True
            for name in ("mongodb_tx_ready", "redis_ready", "media_ready")
        ), "Backend readiness must verify MongoDB, Redis and media; update the backend code first"
        marker = client.get("/compatibility/version")
        assert (
            marker.status_code == 200
            and marker.json().get("sync_cursor") == "signed-v1"
        ), "Backend and smoke script versions differ; extract the full updated ZIP and rebuild Docker"
        root = login(client, username, password)
        root_header = header(root)
        try:
            registered = expect(
                client.post(
                    "/admin/auth/register-owner",
                    json={
                        "username": owner_name,
                        "password": owner_password,
                        "full_name": "Content smoke owner",
                        "email": f"{suffix}@example.com",
                        "phone": "0900000000",
                        "property_name": source["name"],
                        "property_address": source["address"],
                        "national_id": "000000000003",
                    },
                ),
                201,
            )
            created_accounts.append(registered["user"]["id"])
            pending_owner = login(client, owner_name, owner_password)
            expect(
                client.post(
                    "/owner/submissions",
                    json={"kind": "create", "payload": source},
                    headers=header(pending_owner),
                ),
                403,
            )
            expect(
                client.patch(
                    "/admin/registrations/" + registered["registration_id"],
                    json={"status": "approved"},
                    headers=root_header,
                ),
                200,
            )
            owner = login(client, owner_name, owner_password)
            owner_header = header(owner)
            image_data = tiny_png()
            image = expect(
                client.post(
                    "/owner/media/images",
                    headers=owner_header,
                    files={"file": ("sample.png", image_data, "image/png")},
                ),
                201,
            )
            expect(client.get(image["url"]), 404)
            assert (
                client.get(image["preview_url"], headers=owner_header).content
                == image_data
            )
            source["images"] = [image["id"]]
            invalid = client.post(
                "/owner/submissions",
                json={
                    "kind": "create",
                    "payload": source | {"images": [image["id"]] * 9},
                },
                headers=owner_header,
            )
            expect(invalid, 422)
            too_big = client.post(
                "/owner/media/images",
                files={
                    "file": ("large.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")
                },
                headers=owner_header,
            )
            expect(too_big, 413)
            submission = expect(
                client.post(
                    "/owner/submissions",
                    json={"kind": "create", "payload": source},
                    headers=owner_header,
                ),
                201,
            )
            expect(client.get("/admin/submissions", headers=owner_header), 403)
            approved = expect(
                client.patch(
                    "/admin/submissions/" + submission["id"],
                    json={"status": "approved", "admin_note": "Smoke approval"},
                    headers=root_header,
                ),
                200,
            )
            poi_id = approved["poi_id"]
            published = expect(
                client.get("/poi/" + poi_id, params={"language": "fr"}), 200
            )
            assert (
                published["fallback_tier"] == 3
                and published["language"] == "vi"
                and published["audio_url"] is None
            )
            assert client.get(image["url"]).content == image_data
            notes = expect(
                client.get("/owner/notifications", headers=owner_header), 200
            )
            notification = next(
                row
                for row in notes["items"]
                if row["submission_id"] == submission["id"]
            )
            assert notification["is_read"] is False
            expect(
                client.patch(
                    "/owner/notifications/" + notification["id"] + "/read",
                    headers=owner_header,
                ),
                200,
            )
            print(
                "PASS: image validation, pending submission, approval, published POI and owner notifications"
            )

            initial = client.get(
                "/poi/load-all", params={"language": "fr", "limit": 100}
            )
            expect(initial, 200)
            expect(
                client.get(
                    "/poi/load-all",
                    params={"language": "fr", "limit": 100},
                    headers={"If-None-Match": initial.headers["etag"]},
                ),
                304,
            )
            baseline = full_sync(client)
            english = {
                "name": "English stay " + suffix,
                "description": "English description",
                "check_in_instructions": "Check in after 2 PM",
                "source_revision": published["source_revision"],
            }
            expect(
                client.put(
                    f"/admin/pois/{poi_id}/localizations/en",
                    json=english,
                    headers=root_header,
                ),
                200,
            )
            delta = full_sync(client, cursor=baseline["sync_cursor"])
            hydrated = next(row for row in delta["items"] if row["id"] == poi_id)
            assert hydrated["language"] == "en" and hydrated["fallback_tier"] == 2
            expect(
                client.put(
                    f"/admin/pois/{poi_id}/localizations/fr",
                    json=english | {"name": "French stay " + suffix},
                    headers=root_header,
                ),
                200,
            )
            exact = expect(client.get("/poi/" + poi_id, params={"language": "fr"}), 200)
            assert exact["language"] == "fr" and exact["fallback_tier"] == 1
            menu = expect(
                client.post(
                    "/owner/menu-items",
                    json={
                        "poi_id": poi_id,
                        "name": "Double room",
                        "price": "500000.00",
                        "amenities": ["WiFi", "Breakfast"],
                    },
                    headers=owner_header,
                ),
                201,
            )
            expect(
                client.patch(
                    f"/owner/pois/{poi_id}/menu-items/{menu['id']}",
                    json={
                        "expected_revision": 1,
                        "name": "Double room",
                        "price": "600000.00",
                    },
                    headers=owner_header,
                ),
                200,
            )
            current = expect(client.get("/poi/" + poi_id), 200)
            assert current["menu_items"][0]["price"] == "600000.00"
            changed_source = source | {"description": "Updated Vietnamese source"}
            update = expect(
                client.post(
                    "/owner/submissions",
                    json={
                        "kind": "update",
                        "poi_id": poi_id,
                        "expected_revision": current["revision"],
                        "payload": changed_source,
                    },
                    headers=owner_header,
                ),
                201,
            )
            expect(
                client.patch(
                    "/admin/submissions/" + update["id"],
                    json={"status": "approved", "admin_note": "Smoke update"},
                    headers=root_header,
                ),
                200,
            )
            changed = expect(
                client.get("/poi/" + poi_id, params={"language": "fr"}), 200
            )
            assert (
                changed["fallback_tier"] == 3
                and changed["description"] == changed_source["description"]
            )
            nearby = expect(
                client.get(
                    "/poi/nearby",
                    params={
                        "latitude": source["latitude"],
                        "longitude": source["longitude"],
                        "radius_m": 1000,
                        "language": "fr",
                        "limit": 200,
                    },
                ),
                200,
            )
            assert any(row["id"] == poi_id for row in nearby["items"])
            print(
                "PASS: ETag/304, delta sync, room types, reviewed updates and all three language fallbacks"
            )
            print("PASS: nearby search using " + nearby["query_engine"])

            other_name = "other_" + suffix
            second = expect(
                client.post(
                    "/admin/auth/register-owner",
                    json={
                        "username": other_name,
                        "password": owner_password,
                        "full_name": "Other test owner",
                        "email": f"other-{suffix}@example.com",
                        "phone": "0900000000",
                        "property_name": "Other test stay",
                        "property_address": "Test",
                        "national_id": "000000000004",
                    },
                ),
                201,
            )
            created_accounts.append(second["user"]["id"])
            expect(
                client.patch(
                    "/admin/registrations/" + second["registration_id"],
                    json={"status": "approved"},
                    headers=root_header,
                ),
                200,
            )
            second_tokens = login(client, other_name, owner_password)
            expect(
                client.get(
                    f"/owner/pois/{poi_id}/menu-items", headers=header(second_tokens)
                ),
                404,
            )
            expect(client.delete("/poi/" + poi_id, headers=owner_header), 403)
            before_delete = full_sync(client)
            expect(client.delete("/poi/" + poi_id, headers=root_header), 204)
            expect(client.get("/poi/" + poi_id), 404)
            removed = full_sync(client, cursor=before_delete["sync_cursor"])
            assert poi_id in removed["removed_poi_ids"]
            time_delta = expect(
                client.get(
                    "/poi/load-all",
                    params={"updated_after": before_delete["as_of"], "language": "fr"},
                ),
                200,
            )
            assert poi_id in time_delta["removed_poi_ids"]
            jobs = expect(client.get("/admin/media-cleanup", headers=root_header), 200)
            assert any(
                row["asset_id"] == image["id"] and row["reason"] == "poi_deleted"
                for row in jobs
            )
            poi_id = None
            print(
                "PASS: owner isolation, transactional deletion, removed_poi_ids and durable media cleanup intent"
            )
        finally:
            if poi_id:
                client.delete("/poi/" + poi_id, headers=root_header)
            for user_id in created_accounts:
                client.delete("/admin/users/" + user_id, headers=root_header)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--ca-file", default="")
    args = parser.parse_args()
    values = read_values(
        (Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8-sig")
    )
    if not values.get("SUPERADMIN_USERNAME") or not values.get("SUPERADMIN_PASSWORD"):
        raise SystemExit("Configure super-admin credentials in .env first")
    try:
        run(
            args.base_url,
            values["SUPERADMIN_USERNAME"],
            values["SUPERADMIN_PASSWORD"],
            verify=args.ca_file or True,
        )
    except (httpx.HTTPError, AssertionError) as exc:
        raise SystemExit(f"Phase 3 smoke failed: {exc}") from None


if __name__ == "__main__":
    main()
