"""Enable local Docker S3, preserving existing database/JWT settings.

Run from the project root: python scripts/configure_local_s3.py
This uses only Python's standard library.
"""

import argparse
import os
import re
import secrets
import shlex
import tempfile
from pathlib import Path


MANAGED = {
    "MEDIA_BACKEND",
    "S3_ENDPOINT_URL",
    "S3_BUCKET",
    "S3_REGION",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "S3_ADDRESSING_STYLE",
    "COMPOSE_FILE",
    "COMPOSE_PATH_SEPARATOR",
}
LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def read_values(text):
    values = {}
    for line in text.splitlines():
        match = LINE.match(line)
        if not match:
            continue
        key, raw = match.groups()
        if key not in MANAGED | {"APP_ENV"}:
            continue
        try:
            parts = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            raise ValueError(
                f"Cannot parse {key} in .env; no changes were written."
            ) from None
        values[key] = " ".join(parts)
    return values


def configure(root: Path):
    path = root / ".env"
    if not (root / "docker-compose.s3.yml").is_file():
        raise ValueError(
            "docker-compose.s3.yml is missing; extract the complete updated ZIP first."
        )
    source = path if path.exists() else root / ".env.example"
    text = source.read_text(encoding="utf-8-sig")
    existing = read_values(text)
    if existing.get("APP_ENV", "development").lower() not in {
        "dev",
        "development",
        "test",
    }:
        raise ValueError(
            "This helper only configures local development/test environments."
        )
    compose = existing.get("COMPOSE_FILE", "")
    if compose not in {
        "",
        "docker-compose.yml",
        "docker-compose.yml,docker-compose.s3.yml",
        "docker-compose.yml,docker-compose.https.yml",
        "docker-compose.yml,docker-compose.s3.yml,docker-compose.https.yml",
    }:
        raise ValueError(
            "Custom COMPOSE_FILE detected; configure the S3 override manually instead."
        )
    endpoint = existing.get("S3_ENDPOINT_URL", "")
    if endpoint and endpoint != "http://s3:9000":
        raise ValueError(
            "An external S3 endpoint is already configured; no changes were written."
        )
    access = existing.get("S3_ACCESS_KEY", "")
    secret = existing.get("S3_SECRET_KEY", "")
    if bool(access) != bool(secret):
        raise ValueError(
            "S3_ACCESS_KEY and S3_SECRET_KEY must both be present or both empty."
        )
    if access and (
        not re.fullmatch(r"[A-Za-z0-9_-]{3,128}", access)
        or not re.fullmatch(r"[A-Za-z0-9_-]{8,256}", secret)
    ):
        raise ValueError(
            "Existing S3 keys need manual configuration; no keys were changed."
        )
    if not access:
        access = "smartstay-" + secrets.token_hex(8)
        secret = secrets.token_urlsafe(36)
    updates = {
        "MEDIA_BACKEND": "s3",
        "S3_ENDPOINT_URL": "http://s3:9000",
        "S3_BUCKET": existing.get("S3_BUCKET") or "smartstay-media",
        "S3_REGION": "us-east-1",
        "S3_ACCESS_KEY": access,
        "S3_SECRET_KEY": secret,
        "S3_ADDRESSING_STYLE": "path",
        "COMPOSE_PATH_SEPARATOR": ",",
        "COMPOSE_FILE": "docker-compose.yml,docker-compose.s3.yml"
        + (
            ",docker-compose.https.yml"
            if "docker-compose.https.yml" in compose.split(",")
            else ""
        ),
    }
    seen = set()
    output = []
    for line in text.splitlines():
        match = LINE.match(line)
        key = match.group(1) if match else None
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
            mode="w",
            encoding="utf-8",
            dir=root,
            prefix=".env-s3-",
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            file.write("\n".join(output) + "\n")
        os.replace(temp_path, path)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        configure(root)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    print("Local S3 enabled. Existing JWT/database settings were preserved.")
    print("Credentials are stored only in .env; they are not printed here.")
    print("Next: docker compose up -d --build")


if __name__ == "__main__":
    main()
