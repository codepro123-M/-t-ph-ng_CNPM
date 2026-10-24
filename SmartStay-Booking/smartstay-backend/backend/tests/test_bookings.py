from datetime import timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from bson import ObjectId

from app.bookings import service
from app.bookings.schemas import business_today
from test_content import create
from test_phase2 import auth


def customer(client, username="traveller"):
    user = {
        "username": username,
        "full_name": "Khách thử nghiệm",
        "password": "Booking-test-2026",
    }
    assert client.post("/api/v1/auth/register", json=user).status_code == 201
    result = client.post(
        "/api/v1/auth/session",
        json={"username": username, "password": user["password"], "mode": "bearer"},
    )
    assert result.status_code == 200, result.text
    return result.json()


def setup_stay(client, root, *, inventory=1):
    poi = create(client, root)
    response = client.post(
        "/admin/menu-items",
        headers=auth(root),
        json={
            "poi_id": poi["id"],
            "name": "Deluxe",
            "price": "650000.00",
            "capacity": 2,
            "inventory": inventory,
        },
    )
    assert response.status_code == 201, response.text
    room = response.json()
    day = business_today() + timedelta(days=5)
    payload = {
        "request_id": str(uuid4()),
        "poi_id": poi["id"],
        "room_type_id": room["id"],
        "check_in": day.isoformat(),
        "check_out": (day + timedelta(days=2)).isoformat(),
        "guests": 2,
        "contact_name": "Trần Quang Minh",
        "email": "minh@example.com",
        "phone": "0901234567",
        "notes": "Nhận phòng buổi chiều",
    }
    return poi, room, payload


def reserve(client, token, payload):
    return client.post("/bookings", headers=auth(token), json=payload)


def test_booking_is_durable_server_priced_and_visible_to_admin(client, root, services):
    account = customer(client)
    _, _, payload = setup_stay(client, root)
    result = reserve(client, account["access_token"], payload)
    assert result.status_code == 201, result.text
    booking = result.json()
    assert booking["total_price"] == "1300000.00" and booking["status"] == "pending"
    assert (
        services.db.raw.bookings.find_one({"_id": ObjectId(booking["id"])})[
            "customer_id"
        ]
        == account["user"]["id"]
    )
    assert (
        client.get("/bookings", headers=auth(account["access_token"])).json()["items"][
            0
        ]["id"]
        == booking["id"]
    )
    dashboard = client.get("/admin/bookings", headers=auth(root))
    assert dashboard.status_code == 200 and dashboard.json()["summary"]["pending"] == 1
    assert (
        "request_hash" not in dashboard.text
        and dashboard.headers["cache-control"] == "no-store"
    )


def test_booking_authorization_and_customer_isolation(client, root):
    a, b = customer(client, "first"), customer(client, "second")
    _, _, payload = setup_stay(client, root)
    assert client.post("/bookings", json=payload).status_code == 401
    assert reserve(client, root, payload).status_code == 403
    booking = reserve(client, a["access_token"], payload).json()
    assert (
        client.get(
            "/bookings/" + booking["id"], headers=auth(b["access_token"])
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/bookings/" + booking["id"] + "/cancel",
            headers=auth(b["access_token"]),
            json={"expected_revision": 1},
        ).status_code
        == 404
    )
    assert (
        client.get("/admin/bookings", headers=auth(a["access_token"])).status_code
        == 403
    )
    assert client.get("/bookings", headers=auth(b["access_token"])).json()["total"] == 0


def test_inventory_conflict_adjacent_stays_and_cancellation_release(
    client, root, services
):
    user = customer(client)["access_token"]
    _, _, payload = setup_stay(client, root)
    booking = reserve(client, user, payload).json()
    conflict = reserve(client, user, payload | {"request_id": str(uuid4())})
    assert conflict.status_code == 409
    adjacent = payload | {
        "request_id": str(uuid4()),
        "check_in": payload["check_out"],
        "check_out": (business_today() + timedelta(days=9)).isoformat(),
    }
    assert reserve(client, user, adjacent).status_code == 201
    query = {
        k: payload[k]
        for k in ("poi_id", "room_type_id", "check_in", "check_out", "guests")
    }
    assert client.get("/bookings/availability", params=query).json()["remaining"] == 0
    cancelled = client.patch(
        "/bookings/" + booking["id"] + "/cancel",
        headers=auth(user),
        json={"expected_revision": 1},
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert client.get("/bookings/availability", params=query).json()["remaining"] == 1
    assert (
        reserve(client, user, payload | {"request_id": str(uuid4())}).status_code == 201
    )
    assert all(row["reserved"] >= 0 for row in services.db.raw.booking_inventory.find())


def test_idempotency_and_request_reuse_guard(client, root, services):
    user = customer(client)["access_token"]
    _, _, payload = setup_stay(client, root)
    first = reserve(client, user, payload)
    again = reserve(client, user, payload)
    assert again.status_code == 201 and again.json()["id"] == first.json()["id"]
    assert services.db.raw.bookings.count_documents({}) == 1
    assert (
        reserve(client, user, payload | {"notes": "Different request"}).status_code
        == 409
    )


def test_inventory_quantity_and_status_revisions(client, root):
    user = customer(client)["access_token"]
    _, _, payload = setup_stay(client, root, inventory=2)
    one = reserve(client, user, payload).json()
    assert (
        reserve(client, user, payload | {"request_id": str(uuid4())}).status_code == 201
    )
    assert (
        reserve(client, user, payload | {"request_id": str(uuid4())}).status_code == 409
    )
    url = "/admin/bookings/" + one["id"]
    confirmed = client.patch(
        url, headers=auth(root), json={"expected_revision": 1, "status": "confirmed"}
    )
    assert confirmed.status_code == 200 and confirmed.json()["revision"] == 2
    assert (
        client.patch(
            url,
            headers=auth(root),
            json={"expected_revision": 1, "status": "cancelled"},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            url,
            headers=auth(root),
            json={"expected_revision": 2, "status": "completed"},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            url,
            headers=auth(root),
            json={"expected_revision": 2, "status": "cancelled"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            url,
            headers=auth(root),
            json={"expected_revision": 3, "status": "confirmed"},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"total_price": "1"}, 422),
        ({"guests": 3}, 409),
        ({"check_out": (business_today() + timedelta(days=5)).isoformat()}, 422),
        ({"check_in": (business_today() - timedelta(days=1)).isoformat()}, 422),
        ({"check_out": (business_today() + timedelta(days=50)).isoformat()}, 422),
        ({"room_type_id": "bad"}, 422),
        ({"request_id": "bad"}, 422),
    ],
)
def test_invalid_booking_cannot_change_inventory(
    client, root, services, change, expected
):
    user = customer(client)["access_token"]
    _, _, payload = setup_stay(client, root)
    response = reserve(client, user, payload | change)
    assert response.status_code == expected, response.text
    assert services.db.raw.bookings.count_documents({}) == 0
    assert services.db.raw.booking_inventory.count_documents({}) == 0


def test_availability_bad_dates_unpublished_room_and_transaction_rollback(
    client, root, services, monkeypatch
):
    user = customer(client)["access_token"]
    _, room, payload = setup_stay(client, root)
    query = {k: payload[k] for k in ("poi_id", "room_type_id", "check_in", "check_out")}
    assert (
        client.get(
            "/bookings/availability", params=query | {"check_out": payload["check_in"]}
        ).status_code
        == 422
    )
    monkeypatch.setattr(
        service, "audit", AsyncMock(side_effect=RuntimeError("audit failed"))
    )
    with pytest.raises(RuntimeError, match="audit failed"):
        reserve(client, user, payload)
    assert services.db.raw.bookings.count_documents({}) == 0
    assert services.db.raw.booking_inventory.count_documents({}) == 0
    services.db.raw.menu_items.update_one(
        {"_id": ObjectId(room["id"])}, {"$set": {"is_available": False}}
    )
    assert reserve(client, user, payload).status_code == 404


def test_builtin_booking_permissions_migrate_once_without_changing_custom_roles(
    client, services
):
    from app.admin.bootstrap import ensure_roles

    roles = services.db.raw.roles
    roles.update_one(
        {"name": "admin"},
        {
            "$pull": {"permissions": {"$in": ["booking.read", "booking.update"]}},
            "$unset": {"booking_permissions_version": ""},
        },
    )
    old = roles.find_one({"name": "admin"})["version"]
    roles.insert_one({"name": "custom", "permissions": ["poi.read"], "version": 1})
    client.portal.call(ensure_roles)
    assert roles.find_one({"name": "admin"})["version"] == old + 1
    assert "booking.read" in roles.find_one({"name": "admin"})["permissions"]
    client.portal.call(ensure_roles)
    assert roles.find_one({"name": "admin"})["version"] == old + 1
    assert roles.find_one({"name": "custom"})["permissions"] == ["poi.read"]
