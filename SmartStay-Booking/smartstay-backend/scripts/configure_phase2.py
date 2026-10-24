"""Prepare local Phase 2 secrets, explicit bootstrap and HTTPS. Standard library only."""

import os
import re
import secrets
import shlex
import tempfile
from pathlib import Path

LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
PLACEHOLDERS = {
    "",
    "changeme",
    "secret",
    "dev-jwt-secret-key-change-in-production-32chars",
    "dev-refresh-secret-key-change-in-prod-32chars",
    "dev-fernet-and-app-secret-key-change-in-prod",
}
KEYS = {
    "APP_ENV",
    "JWT_SECRET",
    "REFRESH_TOKEN_SECRET",
    "SECRET_KEY",
    "SUPERADMIN_BOOTSTRAP_MODE",
    "SUPERADMIN_USERNAME",
    "SUPERADMIN_PASSWORD",
    "COMPOSE_FILE",
    "COMPOSE_PATH_SEPARATOR",
}


def read_values(text):
    values = {}
    for line in text.splitlines():
        match = LINE.match(line)
        if match and match[1] in KEYS:
            try:
                values[match[1]] = " ".join(shlex.split(match[2], comments=True))
            except ValueError:
                raise ValueError(
                    f"Cannot parse {match[1]}; no changes were written"
                ) from None
    return values


def configure(root: Path, https=True):
    path = root / ".env"
    source = path if path.exists() else root / ".env.example"
    text = source.read_text(encoding="utf-8-sig")
    existing = read_values(text)
    if existing.get("APP_ENV", "development").lower() not in {
        "dev",
        "development",
        "test",
    }:
        raise ValueError("This helper only configures local development/test")
    updates = {}
    for key in ("JWT_SECRET", "REFRESH_TOKEN_SECRET", "SECRET_KEY"):
        value = existing.get(key, "")
        if value in PLACEHOLDERS:
            updates[key] = secrets.token_urlsafe(48)
        elif len(value.strip()) < 32:
            raise ValueError(
                f"Existing {key} is too short; review it manually before changing keys"
            )
    username = existing.get("SUPERADMIN_USERNAME", "") or "superadmin"
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,50}", username):
        raise ValueError("Invalid SUPERADMIN_USERNAME")
    if not existing.get("SUPERADMIN_USERNAME"):
        updates["SUPERADMIN_USERNAME"] = username
    password = existing.get("SUPERADMIN_PASSWORD", "")
    if not password:
        updates["SUPERADMIN_PASSWORD"] = secrets.token_urlsafe(24)
    elif not 8 <= len(password.encode()) <= 72:
        raise ValueError("SUPERADMIN_PASSWORD must contain 8-72 UTF-8 bytes")
    updates["SUPERADMIN_BOOTSTRAP_MODE"] = "env_only"
    compose = existing.get("COMPOSE_FILE", "")
    files = compose.split(",") if compose else ["docker-compose.yml"]
    allowed = {
        "docker-compose.yml",
        "docker-compose.s3.yml",
        "docker-compose.https.yml",
    }
    if set(files) - allowed or files[0] != "docker-compose.yml":
        raise ValueError("Custom COMPOSE_FILE detected; configure Phase 2 manually")
    if https:
        if not (root / "docker-compose.https.yml").is_file():
            raise ValueError("Extract the full ZIP, including docker-compose.https.yml")
        if "docker-compose.https.yml" not in files:
            files.append("docker-compose.https.yml")
    updates.update(COMPOSE_FILE=",".join(files), COMPOSE_PATH_SEPARATOR=",")
    output, seen = [], set()
    for line in text.splitlines():
        match = LINE.match(line)
        key = match[1] if match else None
        if key in updates:
            if key not in seen:
                output.append(f"{key}={updates[key]}")
                seen.add(key)
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in updates.items() if key not in seen)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=root, prefix=".env-phase2-", delete=False
        ) as file:
            temp_path = Path(file.name)
            file.write("\n".join(output) + "\n")
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
    return path


def main():
    try:
        configure(Path(__file__).resolve().parents[1])
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    print(
        "Phase 2 configured. Existing strong keys, database and S3 settings were preserved."
    )
    print(
        "Read SUPERADMIN_USERNAME and SUPERADMIN_PASSWORD in your local .env. Do not share them."
    )
    print("Next: docker compose up -d --build")


if __name__ == "__main__":
    main()
