from datetime import datetime, timezone

import bcrypt
import jwt
import pytest
from bson import ObjectId

from app.core.config import settings

REGISTRATION = {
    "username": "minh",
    "full_name": "Trần Quang Minh",
    "password": "MinhDemo@2026",
}


def register(client):
    response = client.post("/api/v1/auth/register", json=REGISTRATION)
    assert response.status_code == 201, response.text
    return response.json()


def login(client, **changes):
    credentials = {
        "username": REGISTRATION["username"],
        "password": REGISTRATION["password"],
    } | changes
    return client.post("/api/v1/auth/login", data=credentials)


def test_register_login_and_current_user(client, services):
    user = register(client)
    stored = services.users.find_one({"_id": ObjectId(user["id"])})
    assert bcrypt.checkpw(
        REGISTRATION["password"].encode(), stored["password_hash"].encode()
    )
    assert "password_hash" not in user
    response = login(client, username=" MINH ")
    assert response.status_code == 200, response.text
    tokens = response.json()
    assert tokens["expires_in"] == 1800
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + tokens["access_token"]}
    )
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]
    assert me.json()["permissions"] == ["poi.read", "menu.read", "content.read"]
    claims = jwt.decode(
        tokens["access_token"],
        settings.JWT_SECRET,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
    )
    assert claims["exp"] - claims["iat"] == 1800
    refresh = jwt.decode(
        tokens["refresh_token"],
        settings.REFRESH_TOKEN_SECRET,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
    )
    assert refresh["exp"] - refresh["iat"] == 604800


def test_duplicate_username_is_case_insensitive(client):
    register(client)
    assert (
        client.post(
            "/api/v1/auth/register", json=REGISTRATION | {"username": " MINH "}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"password": "short"},
        {"password": "a" * 73},
        {"password": "á" * 37},
        {"full_name": "   "},
        {"username": "bad/name"},
        {"username": "ab"},
        {"role": "admin"},
        {"is_active": True},
    ],
)
def test_invalid_registration_is_rejected(client, services, changes):
    response = client.post("/api/v1/auth/register", json=REGISTRATION | changes)
    assert response.status_code == 422
    assert services.users.count_documents({}) == 0
    assert all("input" not in error for error in response.json()["detail"])
    assert REGISTRATION["password"] not in response.text


@pytest.mark.parametrize("password", ["WrongPass@2026", "a" * 73, "á" * 37, "short"])
def test_wrong_password_is_rejected(client, password):
    register(client)
    response = login(client, password=password)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_unknown_user_and_wrong_password_have_same_error(client):
    register(client)
    missing, wrong = (
        login(client, username="missing"),
        login(client, password="WrongPass@2026"),
    )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()


@pytest.mark.parametrize("authorization", [None, "Bearer broken", "Basic wrong"])
def test_me_requires_valid_credentials(client, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": datetime(2000, 1, 1, tzinfo=timezone.utc)},
        {"type": "refresh"},
        {"sub": "invalid"},
        {"sub": 123},
        {"iat": datetime(2100, 1, 1, tzinfo=timezone.utc)},
        {"aud": "another-app"},
        {"iss": "another-issuer"},
    ],
)
def test_invalid_claims(client, changes):
    register(client)
    claims = jwt.decode(
        login(client).json()["access_token"],
        settings.JWT_SECRET,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
    )
    bad = jwt.encode(claims | changes, settings.JWT_SECRET, algorithm="HS256")
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + bad}
        ).status_code
        == 401
    )


def test_disabled_user_cannot_login(client, services):
    user = register(client)
    services.users.update_one(
        {"_id": ObjectId(user["id"])}, {"$set": {"is_active": False}}
    )
    assert login(client).status_code == 401


def test_openapi_authorize_flow(client):
    schema = client.get("/openapi.json").json()
    assert "/admin/auth/register-owner" in schema["paths"]
    assert (
        schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"][
            "password"
        ]["tokenUrl"]
        == "/api/v1/auth/login"
    )
    assert schema["paths"]["/api/v1/auth/me"]["get"]["security"]
