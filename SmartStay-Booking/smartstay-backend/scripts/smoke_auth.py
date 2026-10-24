"""Run against Docker: create one test user, log in, and verify /me.

The account remains in MongoDB. A random username prevents collisions.
"""

import argparse
import secrets

import httpx


def require_status(response, expected):
    if response.status_code != expected:
        raise SystemExit(
            f"{response.request.method} {response.request.url.path}: "
            f"expected {expected}, got {response.status_code}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    username = "smoke_" + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)

    with httpx.Client(
        base_url=args.base_url.rstrip("/"), timeout=20, trust_env=False
    ) as client:
        registration = {
            "username": username,
            "full_name": "Authentication smoke test",
            "password": password,
        }
        created = client.post("/api/v1/auth/register", json=registration)
        require_status(created, 201)
        duplicate = client.post("/api/v1/auth/register", json=registration)
        require_status(duplicate, 409)
        login = client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": password},
        )
        require_status(login, 200)
        token = login.json()["access_token"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
        require_status(me, 200)
        if me.json()["id"] != created.json()["id"]:
            raise SystemExit("The token returned a different user.")
        require_status(client.get("/api/v1/auth/me"), 401)
    print(f"PASS: register, duplicate rejection, login, /me. Test user: {username}")


if __name__ == "__main__":
    main()
