"""Aliases preserve canonical ObjectId schemas, signed sync and media ownership."""

from test_content import SOURCE
from test_phase2 import auth


def test_poi_aliases_and_legacy_menu_share_canonical_records(client, root):
    made = client.post("/api/v1/poi", json=SOURCE, headers=auth(root))
    assert made.status_code == 201
    poi_id = made.json()["id"]
    assert len(poi_id) == 24
    assert client.get("/api/v1/poi/" + poi_id).json()["id"] == poi_id
    assert client.get("/api/v1/content/poi/" + poi_id).json()["id"] == poi_id
    assert client.get(f"/poi/{poi_id}/menu").json()["items"] == []
    assert client.get("/compatibility/version").json()["storage"] == "mongodb"


def test_alias_sync_uses_frontend_paging_contract(client, root):
    client.post("/poi", json=SOURCE, headers=auth(root))
    page = client.get("/api/v1/poi/load-all?lang=en&limit=1").json()
    assert page["has_more"] is False and page["mode"] == "full"
    assert page["items"][0]["language"] == "vi"
    assert len(page["sync_cursor"]) > 100 and "as_of" in page
    delta = client.get("/poi/load-all", params={"cursor": page["sync_cursor"]}).json()
    assert delta["items"] == [] and delta["removed_poi_ids"] == []


def test_old_arbitrary_media_payload_cannot_bypass_upload_checks(client, root):
    response = client.post(
        "/api/v1/poi",
        json=SOURCE
        | {"images": [{"url": "https://example.com/not-managed.jpg", "size_bytes": 1}]},
        headers=auth(root),
    )
    assert response.status_code == 422
