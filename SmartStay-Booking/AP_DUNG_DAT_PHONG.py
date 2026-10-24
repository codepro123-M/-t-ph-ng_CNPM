"""Apply the booking update to an existing SmartStay checkout with local backups."""

import argparse
import hashlib
import json
import shlex
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath


def env_values(text):
    values = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.lstrip().startswith("#"):
            try:
                parts = shlex.split(value, comments=True)
                values[key.strip().removeprefix("export ")] = parts[0] if parts else ""
            except ValueError:
                raise ValueError("File .env co dong sai dinh dang; hay sua truoc khi cap nhat.") from None
    return values


def local_origins(text):
    values = env_values(text)
    if values.get("APP_ENV", "development").lower() not in {"dev", "development", "test"}:
        return text
    origins = [v.strip() for v in values.get("TRUSTED_ORIGINS", "").split(",") if v.strip()]
    for origin in ("http://localhost:4173", "http://127.0.0.1:4173"):
        if origin not in origins:
            origins.append(origin)
    replacement = "TRUSTED_ORIGINS=" + ",".join(origins)
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.partition("=")[0].strip().removeprefix("export ") == "TRUSTED_ORIGINS":
            ending = "\r\n" if line.endswith("\r\n") else "\n"
            lines[i] = replacement + ending
            return "".join(lines)
    return text.rstrip("\r\n") + "\n" + replacement + "\n"


def apply_update(bundle, target, *, dry_run=False):
    bundle, target = Path(bundle).resolve(), Path(target).resolve()
    if not (target / "docker-compose.yml").is_file() or not (target / "backend/app/main.py").is_file():
        raise ValueError("Chon thu muc backend cu co docker-compose.yml va backend/app/main.py.")
    env = target / ".env"
    if not env.resolve().is_relative_to(target):
        raise ValueError("File .env la lien ket ra ngoai du an; khong thay doi.")
    if not env.is_file():
        raise ValueError("Thu muc nay chua co .env. Hay chon dung thu muc SmartStay dang chay cua ban.")
    manifest = json.loads((bundle / "UPDATE_MANIFEST.json").read_text(encoding="utf-8"))
    sources = []
    for item in manifest["files"]:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or str(relative) == ".env":
            raise ValueError("Manifest khong hop le.")
        source = bundle / "smartstay-backend" / Path(*relative.parts)
        dest = target / Path(*relative.parts)
        if not source.resolve().is_relative_to(bundle / "smartstay-backend") or not dest.resolve().is_relative_to(target):
            raise ValueError("Phat hien duong dan lien ket ra ngoai du an; khong thay doi.")
        if hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("File cap nhat bi thieu hoac thay doi: " + str(relative))
        sources.append((source, dest, Path(*relative.parts)))
    old_env = env.read_text(encoding="utf-8-sig")
    new_env = local_origins(old_env)
    if dry_run:
        return {"files": len(sources), "env_changed": old_env != new_env, "backup": None}
    backup = target / "booking-backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if not backup.resolve().is_relative_to(target):
        raise ValueError("Thu muc sao luu la lien ket ra ngoai du an; khong thay doi.")
    backup.mkdir(parents=True)
    backup.chmod(0o700)
    (backup.parent / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    originals = [(env, backup / ".env")]
    originals += [(dest, backup / relative) for _, dest, relative in sources if dest.is_file()]
    for source, dest in originals:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for source, dest, _ in sources:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != dest.resolve():
            shutil.copy2(source, dest)
    if old_env != new_env:
        env.write_text(new_env, encoding="utf-8")
    return {"files": len(sources), "env_changed": old_env != new_env, "backup": backup}


def main():
    parser = argparse.ArgumentParser(description="Cap nhat dat phong that cho SmartStay; sao luu ma cu va giu du lieu MongoDB.")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    target = args.target
    if target is None:
        target = Path(input("Dan duong dan thu muc BACKEND CU (co docker-compose.yml), roi Enter: ").strip().strip('"'))
    try:
        result = apply_update(Path(__file__).resolve().parent, target, dry_run=args.dry_run)
    except (ValueError, OSError, KeyError) as exc:
        raise SystemExit("KHONG CAP NHAT: " + str(exc)) from None
    print("Da kiem tra" if args.dry_run else "DA CAP NHAT", result["files"], "tep.")
    if result["backup"]:
        print("Ban sao luu ma cu:", result["backup"])
    print("Giu nguyen du lieu MongoDB, Redis va cau hinh S3.")
    print("Tiep theo: mo terminal trong BACKEND CU, chay: docker compose up -d --build backend")


if __name__ == "__main__":
    main()
