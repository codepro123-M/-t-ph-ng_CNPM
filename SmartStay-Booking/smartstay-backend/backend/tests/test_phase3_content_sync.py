"""Legacy request/URL compatibility without weakening ownership or publication."""

from unittest.mock import AsyncMock

import pytest

from app.content import service
from test_content import ENGLISH, SOURCE, create
from test_phase2 import auth, verified_owner


def legacy_source():
    return {
        key: value
        for key, value in SOURCE.items()
        if key not in {"latitude", "longitude"}
    } | {
        "lat": SOURCE["latitude"],
        "lng": SOURCE["longitude"],
        "geofence_radius": 30,
        "trigger_radius": 30,
    }


def test_poi_schema_image_limits_and_geofence_defaults(client, root):
    created = client.post("/poi", json=legacy_source(), headers=auth(root))
    assert created.status_code == 201, created.text
    poi = created.json()
    rejected = client.post("/poi", json=SOURCE | {"lat": -1}, headers=auth(root))
    assert rejected.status_code == 422
    assert client.get("/api/v1/content/poi/" + poi["id"]).status_code == 200
    assert client.get("/api/v1/content/ping").status_code == 200
    assert client.get("/compatibility/version").json()["sync_cursor"] == "signed-v1"


def test_owner_submission_approval_notifications_and_menu_items(client, root):
    tokens, registration = verified_owner(client, root)
    owner_header = auth(tokens["access_token"])
    submitted = client.post(
        "/api/v1/owner/submissions",
        json={"submission_type": "create", "poi_data": legacy_source()},
        headers=owner_header,
    )
    assert submitted.status_code == 201, submitted.text
    reviewed = client.patch(
        "/api/v1/admin/submissions/" + submitted.json()["id"],
        json={"status": "approved", "admin_note": "Reviewed"},
        headers=auth(root),
    )
    assert reviewed.status_code == 200, reviewed.text
    poi_id = reviewed.json()["poi_id"]
    room = client.post(
        f"/api/v1/owner/poi/{poi_id}/menu-items",
        json={"name": "Deluxe", "price": "650000.00", "services": ["Breakfast"]},
        headers=owner_header,
    )
    assert room.status_code == 201, room.text
    assert room.json()["amenities"] == ["Breakfast"]
    menu = client.get(f"/poi/{poi_id}/menu").json()
    assert menu["total"] == 1 and menu["items"][0]["price"] == "650000.00"
    unrelated = create(client, root)
    assert (
        client.post(
            f"/api/v1/owner/poi/{unrelated['id']}/menu-items",
            json={"name": "Foreign room", "price": 1},
            headers=owner_header,
        ).status_code
        == 404
    )
    assert registration["user"]["is_verified"] is False


def test_nearby_haversine_3tier_fallback_delta_sync_and_transactional_delete(
    client, root, services, monkeypatch
):
    poi = create(client, root)
    query = {"lat": SOURCE["latitude"], "lng": SOURCE["longitude"], "lang": "ja"}
    response = client.get("/poi/nearby", params=query)
    assert response.status_code == 200
    assert response.json()["items"][0]["resolved_lang"] == "vi"
    assert response.json()["items"][0]["fallback_tier"] == 3
    translated = client.put(
        f"/poi/{poi['id']}/localizations",
        json=ENGLISH | {"lang": "en"},
        headers=auth(root),
    )
    assert translated.status_code == 200, translated.text
    response = client.get("/poi/nearby", params=query)
    assert response.json()["spatial_engine"] == "haversine_fallback"
    assert response.json()["items"][0]["resolved_lang"] == "en"
    full = client.get("/poi/load-all", params={"lang": "ja"})
    assert (
        client.get(
            "/poi/load-all",
            params={"lang": "ja"},
            headers={"If-None-Match": full.headers["etag"]},
        ).status_code
        == 304
    )
    assert (
        client.get(
            "/poi/load-all",
            params={"lang": "vi"},
            headers={"If-None-Match": full.headers["etag"]},
        ).status_code
        == 200
    )
    checkpoint = full.json()["sync_cursor"]
    original = service.audit
    monkeypatch.setattr(
        service, "audit", AsyncMock(side_effect=RuntimeError("failed audit"))
    )
    with pytest.raises(RuntimeError, match="failed audit"):
        client.delete("/poi/" + poi["id"], headers=auth(root))
    assert services.db.raw.pois.count_documents({}) == 1
    monkeypatch.setattr(service, "audit", original)
    assert client.delete("/poi/" + poi["id"], headers=auth(root)).status_code == 204
    delta = client.get("/poi/load-all", params={"cursor": checkpoint}).json()
    assert delta["removed_poi_ids"] == [poi["id"]] and delta["is_delta"]


def test_legacy_localization_cannot_bypass_moderation_or_media_validation(client, root):
    tokens, registration = verified_owner(client, root)
    poi = create(client, root, {"owner_id": registration["user"]["id"]})
    endpoint = f"/poi/{poi['id']}/localizations"
    assert (
        client.put(
            endpoint,
            json=ENGLISH | {"lang": "en"},
            headers=auth(tokens["access_token"]),
        ).status_code
        == 403
    )
    assert (
        client.put(
            endpoint,
            json=ENGLISH
            | {"lang": "en", "audio_url": "https://unmanaged.example/audio.mp3"},
            headers=auth(root),
        ).status_code
        == 422
    )
