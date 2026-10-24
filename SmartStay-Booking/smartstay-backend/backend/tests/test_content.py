import io
from datetime import timedelta
from unittest.mock import AsyncMock

import jwt
import pytest
from bson import ObjectId
from PIL import Image

from app.content import media, service
from app.content.sync import cursor_key
from app.core.config import MAX_IMAGE_SIZE_BYTES
from app.core.security import utcnow
from test_phase2 import OWNER, admin_login, approve, auth, new_owner, verified_owner

SOURCE = {
    "name": "Homestay Bên Biển",
    "description": "Lưu trú yên tĩnh gần biển Đà Nẵng.",
    "check_in_instructions": "Nhận phòng từ 14 giờ.",
    "category": "homestay",
    "address": "Đà Nẵng",
    "latitude": 16.0544,
    "longitude": 108.2022,
}
ENGLISH = {
    "name": "Seaside Stay",
    "description": "A quiet homestay near the beach.",
    "check_in_instructions": "Check in after 2 PM.",
    "source_revision": 1,
}


@pytest.fixture
def owner_account(client, root):
    return verified_owner(client, root)


def create(client, root, changes=None):
    response = client.post("/poi", json=SOURCE | (changes or {}), headers=auth(root))
    assert response.status_code == 201, response.text
    return response.json()


def image_bytes():
    file = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(file, "PNG")
    return file.getvalue()


def upload(client, token, owner=False):
    response = client.post(
        "/owner/media/images" if owner else "/admin/media/images",
        headers=auth(token),
        files={"file": ("../../unsafe.html", image_bytes(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def approve_content(client, root, submission_id, status="approved"):
    response = client.patch(
        "/admin/submissions/" + submission_id,
        json={"status": status, "admin_note": "Đã kiểm tra"},
        headers=auth(root),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_pending_submission_approval_notifications_and_source_schema(
    client, services, root, owner_account
):
    owner, _ = owner_account
    before = client.get("/poi/load-all").json()
    response = client.post(
        "/owner/submissions",
        json={"kind": "create", "payload": SOURCE},
        headers=auth(owner["access_token"]),
    )
    assert response.status_code == 201, response.text
    submission = response.json()
    assert submission["status"] == "pending"
    assert client.get("/poi/load-all").json()["items"] == []
    assert (
        client.get(
            "/admin/submissions", headers=auth(owner["access_token"])
        ).status_code
        == 403
    )
    reviewed = approve_content(client, root, submission["id"])
    poi_id = reviewed["poi_id"]
    poi = client.get("/poi/" + poi_id).json()
    assert poi["source_language"] == poi["language"] == "vi"
    assert poi["geofence_radius"] == poi["trigger_radius"] == 30
    assert poi["location"]["coordinates"] == [SOURCE["longitude"], SOURCE["latitude"]]
    assert "admin_note" not in poi and "owner_id" not in poi
    stored = services.db.raw.pois.find_one({"_id": ObjectId(poi_id)})
    assert stored["admin_note"] == "Đã kiểm tra"
    delta = client.get("/poi/load-all", params={"cursor": before["sync_cursor"]}).json()
    assert delta["items"][0]["id"] == poi_id
    notes = client.get(
        "/owner/notifications", headers=auth(owner["access_token"])
    ).json()
    assert notes["unread_count"] == 1 and notes["items"][0]["is_read"] is False
    note_id = notes["items"][0]["id"]
    assert (
        client.patch(
            f"/owner/notifications/{note_id}/read", headers=auth(owner["access_token"])
        ).json()["is_read"]
        is True
    )
    assert (
        client.get("/owner/notifications", headers=auth(owner["access_token"])).json()[
            "unread_count"
        ]
        == 0
    )
    assert (
        client.patch(
            "/admin/submissions/" + submission["id"],
            json={"status": "approved"},
            headers=auth(root),
        ).status_code
        == 409
    )
    assert services.db.raw.pois.count_documents({}) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"latitude": 91},
        {"longitude": -181},
        {"name": " "},
        {"category": "restaurant"},
        {"trigger_radius": 0},
        {"audio_priority": -1},
        {"images": [str(ObjectId()) for _ in range(9)]},
        {"images": ["not-an-id"]},
        {"images": ["a" * 24, "a" * 24]},
        {"owner_id": "wrong"},
    ],
)
def test_invalid_poi_schema(client, root, changes):
    response = client.post("/poi", json=SOURCE | changes, headers=auth(root))
    assert response.status_code == 422


def test_radius_alias_and_partial_update_preserve_ownership(
    client, root, owner_account
):
    _, registration = owner_account
    poi = create(
        client, root, {"owner_id": registration["user"]["id"], "trigger_radius": 75}
    )
    assert poi["geofence_radius"] == 75
    changed = client.patch(
        "/poi/" + poi["id"],
        json={"expected_revision": 1, "audio_priority": 8},
        headers=auth(root),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["owner_id"] == registration["user"]["id"]
    assert changed.json()["description"] == SOURCE["description"]
    assert changed.json()["geofence_radius"] == 75
    assert (
        client.patch(
            "/poi/" + poi["id"],
            json={"expected_revision": 1, "name": "Stale"},
            headers=auth(root),
        ).status_code
        == 409
    )


def test_owner_must_use_moderation_and_cannot_update_other_owner_poi(
    client, root, owner_account
):
    owner, registration = owner_account
    own = create(client, root, {"owner_id": registration["user"]["id"]})
    foreign = create(client, root)
    assert (
        client.patch(
            "/poi/" + own["id"],
            json={"expected_revision": 1, "name": "Bypass"},
            headers=auth(owner["access_token"]),
        ).status_code
        == 403
    )
    response = client.post(
        "/owner/submissions",
        json={
            "kind": "update",
            "poi_id": foreign["id"],
            "expected_revision": 1,
            "payload": SOURCE,
        },
        headers=auth(owner["access_token"]),
    )
    assert response.status_code == 404
    assert (
        client.delete(
            "/poi/" + own["id"], headers=auth(owner["access_token"])
        ).status_code
        == 403
    )


def test_submission_stale_revision_does_not_overwrite_and_can_be_rejected(
    client, root, owner_account
):
    owner, registration = owner_account
    poi = create(client, root, {"owner_id": registration["user"]["id"]})
    pending = client.post(
        "/owner/submissions",
        json={
            "kind": "update",
            "poi_id": poi["id"],
            "expected_revision": 1,
            "payload": SOURCE | {"name": "Owner edit"},
        },
        headers=auth(owner["access_token"]),
    ).json()
    assert (
        client.patch(
            "/poi/" + poi["id"],
            json={"expected_revision": 1, "name": "Newer admin edit"},
            headers=auth(root),
        ).status_code
        == 200
    )
    failed = client.patch(
        "/admin/submissions/" + pending["id"],
        json={"status": "approved"},
        headers=auth(root),
    )
    assert failed.status_code == 409
    assert client.get("/poi/" + poi["id"]).json()["name"] == "Newer admin edit"
    assert (
        approve_content(client, root, pending["id"], "rejected")["admin_note"]
        == "Đã kiểm tra"
    )


def test_unverified_owner_blocked_and_mid_request_deactivation_rechecked(
    client, services, root
):
    registration = new_owner(client)
    tokens = admin_login(client, OWNER["username"], OWNER["password"])
    assert (
        client.post(
            "/owner/submissions",
            json={"kind": "create", "payload": SOURCE},
            headers=auth(tokens["access_token"]),
        ).status_code
        == 403
    )
    approve(client, root, registration)
    tokens = admin_login(client, OWNER["username"], OWNER["password"])
    services.db.raw.admin_users.update_one(
        {"username": OWNER["username"]}, {"$set": {"is_active": False}}
    )
    assert (
        client.post(
            "/owner/submissions",
            json={"kind": "create", "payload": SOURCE},
            headers=auth(tokens["access_token"]),
        ).status_code
        == 409
    )


def test_notifications_and_assets_are_owner_scoped(client, root, owner_account):
    first, _ = owner_account
    image = upload(client, first["access_token"], owner=True)
    pending = client.post(
        "/owner/submissions",
        json={"kind": "create", "payload": SOURCE},
        headers=auth(first["access_token"]),
    ).json()
    approve_content(client, root, pending["id"])
    note = client.get(
        "/owner/notifications", headers=auth(first["access_token"])
    ).json()["items"][0]
    second_registration = new_owner(client, "owner_second")
    approve(client, root, second_registration)
    second = admin_login(client, "owner_second", OWNER["password"])["access_token"]
    assert (
        client.get("/owner/notifications", headers=auth(second)).json()["items"] == []
    )
    assert (
        client.patch(
            f"/owner/notifications/{note['id']}/read", headers=auth(second)
        ).status_code
        == 404
    )
    assert (
        client.get("/owner/media/" + image["id"], headers=auth(second)).status_code
        == 404
    )
    assert (
        client.post(
            "/owner/submissions",
            json={"kind": "create", "payload": SOURCE | {"images": [image["id"]]}},
            headers=auth(second),
        ).status_code
        == 403
    )


def test_menu_items_mutations_delta_and_owner_isolation(client, root, owner_account):
    owner, registration = owner_account
    poi = create(client, root, {"owner_id": registration["user"]["id"]})
    checkpoint = client.get("/poi/load-all").json()["sync_cursor"]
    data = {
        "poi_id": poi["id"],
        "name": "Phòng đôi",
        "price": "500000.25",
        "amenities": ["WiFi", "Điều hòa"],
    }
    created = client.post(
        "/owner/menu-items", json=data, headers=auth(owner["access_token"])
    )
    assert created.status_code == 201, created.text
    menu = created.json()
    assert menu["price"] == "500000.25"
    delta = client.get("/poi/load-all", params={"cursor": checkpoint}).json()
    assert delta["items"][0]["menu_items"][0]["id"] == menu["id"]
    updated = client.patch(
        f"/owner/pois/{poi['id']}/menu-items/{menu['id']}",
        json={"expected_revision": 1, "name": "Room", "price": "600000.00"},
        headers=auth(owner["access_token"]),
    )
    assert updated.status_code == 200
    assert client.get(f"/poi/{poi['id']}/menu-items").json()[0]["revision"] == 2
    foreign = create(client, root)
    assert (
        client.post(
            "/owner/menu-items",
            json=data | {"poi_id": foreign["id"]},
            headers=auth(owner["access_token"]),
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/owner/pois/{poi['id']}/menu-items/{menu['id']}",
            headers=auth(owner["access_token"]),
        ).status_code
        == 204
    )
    assert client.get(f"/poi/{poi['id']}/menu-items").json() == []


@pytest.mark.parametrize("price", ["NaN", "-1", "1.001", "999999999999999.99"])
def test_invalid_money_rejected(client, root, price):
    poi = create(client, root)
    assert (
        client.post(
            "/admin/menu-items",
            json={"poi_id": poi["id"], "name": "Room", "price": price},
            headers=auth(root),
        ).status_code
        == 422
    )


def test_three_tier_fallback_nearby_and_translation_invalidated_on_text_change(
    client, root
):
    poi = create(client, root)
    url = f"/admin/pois/{poi['id']}/localizations/"
    missing = client.get("/poi/load-all", params={"language": "fr"}).json()["items"][0]
    assert (missing["language"], missing["fallback_tier"], missing["audio_url"]) == (
        "vi",
        3,
        None,
    )
    assert client.put(url + "en", json=ENGLISH, headers=auth(root)).status_code == 200
    french = client.get("/poi/load-all", params={"language": "fr"}).json()["items"][0]
    assert (french["language"], french["fallback_tier"], french["name"]) == (
        "en",
        2,
        ENGLISH["name"],
    )
    assert (
        client.put(
            url + "fr", json=ENGLISH | {"name": "Maison française"}, headers=auth(root)
        ).status_code
        == 200
    )
    exact = client.get("/poi/load-all", params={"language": "fr"}).json()["items"][0]
    assert exact["language"] == "fr" and exact["fallback_tier"] == 1
    nearby = client.get(
        "/poi/nearby",
        params={
            "latitude": SOURCE["latitude"],
            "longitude": SOURCE["longitude"],
            "language": "fr",
        },
    ).json()
    assert nearby["query_engine"] == "haversine"
    assert nearby["items"][0]["name"] == "Maison française"
    assert nearby["items"][0]["distance_m"] == 0
    current = client.get("/poi/" + poi["id"]).json()
    updated = client.patch(
        "/poi/" + poi["id"],
        json={"expected_revision": current["revision"], "description": "Nội dung mới"},
        headers=auth(root),
    )
    assert updated.status_code == 200
    missing = client.get("/poi/load-all", params={"language": "fr"}).json()["items"][0]
    assert missing["fallback_tier"] == 3 and missing["audio_url"] is None
    assert client.put(url + "en", json=ENGLISH, headers=auth(root)).status_code == 409


def test_etag_conditional_and_language_variants(client, root):
    create(client, root)
    first = client.get("/poi/load-all", params={"language": "vi"})
    etag = first.headers["etag"]
    cached = client.get(
        "/poi/load-all",
        params={"language": "vi"},
        headers={"If-None-Match": '"other", ' + etag.removeprefix("W/")},
    )
    assert cached.status_code == 304 and cached.content == b""
    assert (
        client.get(
            "/poi/load-all", params={"language": "en"}, headers={"If-None-Match": etag}
        ).status_code
        == 200
    )
    assert (
        client.get("/poi/load-all", headers={"If-None-Match": "*"}).status_code == 304
    )
    cors = client.get("/poi/load-all", headers={"Origin": "https://localhost:8443"})
    assert "ETag" in cors.headers["access-control-expose-headers"]


def test_stable_pagination_then_delta_contains_concurrent_update_delete_and_create(
    client, root
):
    first, second, third = [create(client, root, {"name": str(i)}) for i in range(3)]
    page = client.get("/poi/load-all", params={"limit": 1}).json()
    frozen = page["dataset_version"]
    assert page["items"][0]["id"] == first["id"]
    assert (
        client.patch(
            "/poi/" + second["id"],
            json={"expected_revision": 1, "name": "Updated second"},
            headers=auth(root),
        ).status_code
        == 200
    )
    assert client.delete("/poi/" + third["id"], headers=auth(root)).status_code == 204
    fourth = create(client, root, {"name": "Created during sync"})
    second_page = client.get(
        "/poi/load-all",
        params={"cursor": page["sync_cursor"]},
        headers={"If-None-Match": "*"},
    ).json()
    assert second_page["dataset_version"] == frozen
    assert second_page["items"][0]["name"] == "1"
    last = client.get(
        "/poi/load-all", params={"cursor": second_page["sync_cursor"]}
    ).json()
    assert last["items"][0]["id"] == third["id"] and not last["has_more"]
    delta = client.get("/poi/load-all", params={"cursor": last["sync_cursor"]}).json()
    assert {row["id"] for row in delta["items"]} == {second["id"], fourth["id"]}
    assert delta["removed_poi_ids"] == [third["id"]]
    assert (
        next(row for row in delta["items"] if row["id"] == second["id"])["name"]
        == "Updated second"
    )
    empty = client.get("/poi/load-all", params={"cursor": delta["sync_cursor"]}).json()
    assert empty["items"] == empty["removed_poi_ids"] == []


def test_updated_after_exact_boundary_and_unpublish_republish(client, root):
    poi = create(client, root)
    initial = client.get("/poi/load-all").json()
    assert initial["as_of"].endswith(("Z", "+00:00"))
    assert (
        client.get("/poi/load-all", params={"updated_after": initial["as_of"]}).json()[
            "items"
        ]
        == []
    )
    assert (
        client.patch(
            "/poi/" + poi["id"],
            json={"expected_revision": 1, "is_active": False},
            headers=auth(root),
        ).status_code
        == 200
    )
    delta = client.get(
        "/poi/load-all", params={"updated_after": initial["as_of"]}
    ).json()
    assert delta["removed_poi_ids"] == [poi["id"]]
    assert client.get("/poi/" + poi["id"]).status_code == 404
    assert (
        client.patch(
            "/poi/" + poi["id"],
            json={"expected_revision": 2, "is_active": True},
            headers=auth(root),
        ).status_code
        == 200
    )
    assert (
        client.get("/poi/load-all", params={"cursor": delta["sync_cursor"]}).json()[
            "items"
        ][0]["id"]
        == poi["id"]
    )
    assert (
        client.get(
            "/poi/load-all", params={"updated_after": "2026-01-01T00:00:00"}
        ).status_code
        == 422
    )


def test_cursor_tamper_language_page_size_and_dataset_reset(client, services, root):
    create(client, root)
    create(client, root)
    response = client.get("/poi/load-all", params={"limit": 1})
    token = response.json()["sync_cursor"]
    assert (
        client.get("/poi/load-all", params={"cursor": token + "x"}).status_code == 400
    )
    assert (
        client.get(
            "/poi/load-all", params={"cursor": token, "language": "en"}
        ).status_code
        == 400
    )
    assert (
        client.get("/poi/load-all", params={"cursor": token, "limit": 2}).status_code
        == 400
    )
    assert (
        client.get(
            "/poi/load-all",
            params={"cursor": token, "updated_after": "2026-01-01T00:00:00Z"},
        ).status_code
        == 400
    )
    claims = jwt.decode(
        token, cursor_key(), algorithms=["HS256"], audience="smartstay-content-sync"
    )
    expired = jwt.encode(claims | {"exp": 1}, cursor_key(), algorithm="HS256")
    assert client.get("/poi/load-all", params={"cursor": expired}).status_code == 400
    services.db.raw.content_dataset_versions.update_one(
        {"_id": "poi"}, {"$set": {"dataset_id": "reset"}}
    )
    assert client.get("/poi/load-all", params={"cursor": token}).status_code == 409


def test_sync_page_deadline_is_not_extended_by_continuations(client, root):
    for index in range(4):
        create(client, root, {"name": str(index)})
    page = client.get("/poi/load-all", params={"limit": 1}).json()
    claims = jwt.decode(
        page["sync_cursor"],
        cursor_key(),
        algorithms=["HS256"],
        audience="smartstay-content-sync",
    )
    deadline = int((utcnow() + timedelta(minutes=15)).timestamp())
    token = jwt.encode(claims | {"exp": deadline}, cursor_key(), algorithm="HS256")
    next_page = client.get("/poi/load-all", params={"cursor": token})
    assert next_page.status_code == 200 and next_page.json()["has_more"]
    next_claims = jwt.decode(
        next_page.json()["sync_cursor"],
        cursor_key(),
        algorithms=["HS256"],
        audience="smartstay-content-sync",
    )
    assert next_claims["exp"] == deadline


def test_publishing_draft_publishes_its_existing_localized_audio(
    client, services, root, monkeypatch
):
    monkeypatch.setattr(
        media, "inspect_audio", lambda data: {"content_type": "audio/mpeg", "suffix": ".mp3"}
    )
    audio = client.post(
        "/admin/media/audio",
        headers=auth(root),
        files={"file": ("sample.mp3", b"test-audio", "audio/mpeg")},
    )
    assert audio.status_code == 201, audio.text
    asset_id = audio.json()["id"]
    poi = create(client, root, {"is_active": False})
    localized = client.put(
        f"/admin/pois/{poi['id']}/localizations/en",
        json=ENGLISH | {"audio_asset_id": asset_id},
        headers=auth(root),
    )
    assert localized.status_code == 200
    assert client.get("/media/" + asset_id).status_code == 404
    published = client.patch(
        "/poi/" + poi["id"],
        json={"expected_revision": 2, "is_active": True},
        headers=auth(root),
    )
    assert published.status_code == 200
    item = client.get("/poi/" + poi["id"], params={"language": "fr"}).json()
    assert item["fallback_tier"] == 2
    assert client.get(item["audio_url"]).content == b"test-audio"
    assert services.db.raw.media_assets.find_one({"_id": ObjectId(asset_id)})["is_public"]


def test_nearby_radius_and_distance_order_across_antimeridian(client, root):
    near = create(client, root, {"latitude": 0, "longitude": 179.999})
    far = create(client, root, {"latitude": 0, "longitude": 179.0})
    other_side = create(client, root, {"latitude": 0, "longitude": -179.999})
    result = client.get(
        "/poi/nearby",
        params={"latitude": 0, "longitude": 180, "radius_m": 1000, "limit": 2},
    ).json()
    assert {row["id"] for row in result["items"]} == {near["id"], other_side["id"]}
    assert all(row["id"] != far["id"] for row in result["items"])
    assert result["items"][0]["distance_m"] <= result["items"][1]["distance_m"]
    assert service.haversine(0, 0, 0, 180) == pytest.approx(20015114.442, rel=0.00001)


def test_upload_validation_private_preview_publish_and_cleanup(
    client, services, root, owner_account
):
    owner, registration = owner_account
    image = upload(client, owner["access_token"], owner=True)
    asset_id = image["id"]
    assert client.get(image["url"]).status_code == 404
    assert (
        client.get(image["preview_url"], headers=auth(owner["access_token"])).content
        == image_bytes()
    )
    path = media.local_path(
        services.db.raw.media_assets.find_one({"_id": ObjectId(asset_id)})
    )
    assert path.is_file() and path.suffix == ".png"
    assert "unsafe" not in str(path)
    poi = create(
        client, root, {"owner_id": registration["user"]["id"], "images": [asset_id]}
    )
    public = client.get(image["url"])
    assert public.status_code == 200 and public.content == image_bytes()
    assert public.headers["x-content-type-options"] == "nosniff"
    services.db.raw.media_cleanup_jobs.update_many(
        {}, {"$set": {"run_after": utcnow() - timedelta(seconds=1)}}
    )
    assert client.portal.call(media.cleanup_once) == 0  # referenced asset is protected
    assert path.is_file()
    assert client.delete("/poi/" + poi["id"], headers=auth(root)).status_code == 204
    assert path.is_file()  # file deletion happens after commit and grace period
    services.db.raw.media_cleanup_jobs.update_many(
        {}, {"$set": {"run_after": utcnow() - timedelta(seconds=1)}}
    )
    assert client.portal.call(media.cleanup_once) == 1
    assert not path.exists()
    assert client.get(image["url"]).status_code == 404
    assert (
        services.db.raw.media_cleanup_jobs.find_one({"asset_id": asset_id})["state"]
        == "completed"
    )


@pytest.mark.parametrize(
    "data,mime,expected",
    [
        (b"not an image", "image/png", 415),
        (b"\x89PNG\r\n\x1a\n", "image/png", 415),
        (b"x" * (MAX_IMAGE_SIZE_BYTES + 1), "image/png", 413),
    ],
)
def test_upload_invalid_or_over_size(client, root, data, mime, expected):
    response = client.post(
        "/admin/media/images",
        headers=auth(root),
        files={"file": ("picture.png", data, mime)},
    )
    assert response.status_code == expected


def test_delete_cascades_menu_localizations_pending_jobs_and_delta(
    client, services, root, owner_account
):
    owner, registration = owner_account
    image = upload(client, owner["access_token"], owner=True)
    poi = create(
        client, root, {"owner_id": registration["user"]["id"], "images": [image["id"]]}
    )
    assert (
        client.post(
            "/owner/menu-items",
            json={"poi_id": poi["id"], "name": "Room", "price": 1},
            headers=auth(owner["access_token"]),
        ).status_code
        == 201
    )
    assert (
        client.put(
            f"/admin/pois/{poi['id']}/localizations/en",
            json=ENGLISH,
            headers=auth(root),
        ).status_code
        == 200
    )
    current = client.get("/poi/" + poi["id"]).json()
    pending = client.post(
        "/owner/submissions",
        json={
            "kind": "update",
            "poi_id": poi["id"],
            "expected_revision": current["revision"],
            "payload": SOURCE,
        },
        headers=auth(owner["access_token"]),
    )
    assert pending.status_code == 201
    checkpoint = client.get("/poi/load-all").json()["sync_cursor"]
    assert client.delete("/poi/" + poi["id"], headers=auth(root)).status_code == 204
    for name in ("menu_items", "poi_localizations"):
        assert services.db.raw[name].count_documents({"poi_id": poi["id"]}) == 0
    assert services.db.raw.poi_submissions.find_one()["status"] == "cancelled"
    assert (
        services.db.raw.media_cleanup_jobs.find_one({"asset_id": image["id"]})["reason"]
        == "poi_deleted"
    )
    assert client.get("/poi/load-all", params={"cursor": checkpoint}).json()[
        "removed_poi_ids"
    ] == [poi["id"]]


def test_audit_failure_rolls_back_poi_deletion_dataset_and_cleanup_intent(
    client, services, root, monkeypatch
):
    image = upload(client, root)
    poi = create(client, root, {"images": [image["id"]]})
    version = services.db.raw.content_dataset_versions.find_one()["version"]
    original_job = services.db.raw.media_cleanup_jobs.find_one()
    monkeypatch.setattr(
        service, "audit", AsyncMock(side_effect=RuntimeError("audit failed"))
    )
    with pytest.raises(RuntimeError, match="audit failed"):
        client.delete("/poi/" + poi["id"], headers=auth(root))
    assert services.db.raw.pois.count_documents({}) == 1
    assert services.db.raw.content_dataset_versions.find_one()["version"] == version
    assert services.db.raw.content_changes.count_documents({"operation": "remove"}) == 0
    assert (
        services.db.raw.media_cleanup_jobs.find_one()["reason"]
        == original_job["reason"]
    )


def test_approval_notification_failure_rolls_back_everything(
    client, services, root, owner_account, monkeypatch
):
    owner, _ = owner_account
    pending = client.post(
        "/owner/submissions",
        json={"kind": "create", "payload": SOURCE},
        headers=auth(owner["access_token"]),
    ).json()
    monkeypatch.setattr(
        service, "notify", AsyncMock(side_effect=RuntimeError("notifications down"))
    )
    with pytest.raises(RuntimeError, match="notifications down"):
        approve_content(client, root, pending["id"])
    assert services.db.raw.pois.count_documents({}) == 0
    assert services.db.raw.poi_submissions.find_one()["status"] == "pending"
    assert services.db.raw.content_dataset_versions.find_one()["version"] == 0
    assert services.db.raw.content_changes.count_documents({}) == 0


def test_cleanup_failure_is_retained_and_retried(client, services, root, monkeypatch):
    image = upload(client, root)
    services.db.raw.media_cleanup_jobs.update_many(
        {}, {"$set": {"run_after": utcnow() - timedelta(seconds=1)}}
    )
    monkeypatch.setattr(
        media,
        "delete_blob",
        lambda asset: (_ for _ in ()).throw(OSError("disk unavailable")),
    )
    assert client.portal.call(media.cleanup_once) == 0
    job = services.db.raw.media_cleanup_jobs.find_one({"asset_id": image["id"]})
    assert (
        job["state"] == "pending"
        and job["attempts"] == 1
        and job["last_error"] == "OSError"
    )
    assert services.db.raw.media_assets.find_one()["state"] == "deleting"
