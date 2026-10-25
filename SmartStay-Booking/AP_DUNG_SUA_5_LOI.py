"""Apply the verified full-stack repair, backing up code and preserving local settings."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from AP_DUNG_DAT_PHONG import local_origins

SECTIONS = {
    "files": "smartstay-backend",
    "frontend_files": "quickstay-frontend",
    "root_files": "",
}
EXCLUDED = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "__pycache__",
    "runtime_data",
    "booking-backups",
    "repair-backups",
    "dev-certs",
}


def checked_path(root, relative):
    relative = str(relative)
    path = PurePosixPath(relative)
    if (
        not relative
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in relative
        or ":" in relative
        or any(part in EXCLUDED for part in path.parts)
        or (path.name.startswith(".env") and path.name != ".env.example")
    ):
        raise ValueError("Duong dan manifest khong hop le: " + relative)
    result = root / Path(*path.parts)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("Duong dan lien ket ra ngoai du an: " + relative)
    return result


def verify_sources(bundle):
    bundle = Path(bundle).resolve()
    manifest = json.loads((bundle / "UPDATE_MANIFEST.json").read_text(encoding="utf-8"))
    records = []
    for section, folder in SECTIONS.items():
        if not (bundle / folder).resolve().is_relative_to(bundle):
            raise ValueError("Thu muc nguon la lien ket ra ngoai goi cap nhat")
        seen = set()
        for item in manifest.get(section, []):
            relative = item["path"]
            if relative in seen:
                raise ValueError("Manifest trung duong dan: " + relative)
            seen.add(relative)
            source = checked_path(bundle / folder, relative)
            if (
                not source.is_file()
                or hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]
            ):
                raise ValueError(
                    "File cap nhat bi thieu hoac thay doi: " + folder + "/" + relative
                )
            records.append((section, relative, source))
    if not manifest.get("files") or not manifest.get("frontend_files"):
        raise ValueError("Goi cap nhat phai co ca backend va frontend")
    return records


def atomic_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="smartstay-code-", dir=destination.parent
    )
    os.close(descriptor)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def apply_repair(bundle, backend, frontend, *, project=None, dry_run=False):
    bundle, backend, frontend = (
        Path(value).resolve() for value in (bundle, backend, frontend)
    )
    project = Path(project).resolve() if project else None
    if backend == frontend:
        raise ValueError("Thu muc backend va frontend phai khac nhau")
    if (
        backend == bundle / "smartstay-backend"
        or frontend == bundle / "quickstay-frontend"
    ):
        raise ValueError(
            "Hay giai nen ban sua vao thu muc rieng, khong chon chinh goi cap nhat"
        )
    if (
        not (backend / "docker-compose.yml").is_file()
        or not (backend / "backend/app/main.py").is_file()
    ):
        raise ValueError("Chon backend cu co docker-compose.yml va backend/app/main.py")
    if not (frontend / "package.json").is_file():
        raise ValueError("Chon frontend React cu co package.json")
    env = backend / ".env"
    if not env.is_file() or not env.resolve().is_relative_to(backend):
        raise ValueError("Backend cu phai co .env hop le trong thu muc du an")
    roots = {"files": backend, "frontend_files": frontend, "root_files": project}
    plan = []
    for section, relative, source in verify_sources(bundle):
        target_root = roots[section]
        if target_root is None:
            continue
        destination = checked_path(target_root, relative)
        if destination.exists() and not destination.is_file():
            raise ValueError("File cap nhat trung voi thu muc: " + str(destination))
        plan.append((source, destination, SECTIONS[section] or "root", relative))
    if project:
        manifest_target = checked_path(project, "UPDATE_MANIFEST.json")
        plan.append(
            (
                bundle / "UPDATE_MANIFEST.json",
                manifest_target,
                "root",
                "UPDATE_MANIFEST.json",
            )
        )
    old_env = env.read_text(encoding="utf-8-sig")
    new_env = local_origins(old_env)
    if dry_run:
        return {"files": len(plan), "env_changed": old_env != new_env, "backup": None}
    backup_parent = project or backend
    backup = (
        backup_parent
        / "repair-backups"
        / (datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3))
    )
    if not backup.resolve().is_relative_to(backup_parent):
        raise ValueError("Thu muc sao luu la lien ket ra ngoai du an")
    backup.mkdir(parents=True)
    backup.chmod(0o700)
    (backup.parent / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    originals = {}
    for _, destination, folder, relative in plan:
        if destination.is_file():
            saved = backup / folder / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
            originals[destination] = saved
    saved_env = backup / "smartstay-backend/.env"
    saved_env.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(env, saved_env)
    originals[env] = saved_env
    applied = []
    try:
        for source, destination, _, _ in plan:
            atomic_copy(source, destination)
            applied.append(destination)
        if old_env != new_env:
            # The backup already contains the original environment, including keys.
            applied.append(env)
            descriptor, temporary = tempfile.mkstemp(prefix=".env-repair-", dir=backend)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    output.write(new_env)
                os.chmod(temporary, env.stat().st_mode & 0o777)
                os.replace(temporary, env)
            finally:
                Path(temporary).unlink(missing_ok=True)
    except Exception:
        for destination in reversed(applied):
            if destination in originals:
                shutil.copy2(originals[destination], destination)
            else:
                destination.unlink(missing_ok=True)
        raise
    return {"files": len(plan), "env_changed": old_env != new_env, "backup": backup}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        type=Path,
        help="Thu muc cu chua smartstay-backend va quickstay-frontend",
    )
    parser.add_argument(
        "--backend", type=Path, help="Duong dan backend cu, neu hai du an nam rieng"
    )
    parser.add_argument(
        "--frontend", type=Path, help="Duong dan frontend cu, neu hai du an nam rieng"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.project and (args.backend or args.frontend):
        parser.error("Dung --project hoac cap --backend/--frontend")
    project = args.project
    if project is None and not args.backend and not args.frontend:
        project = Path(
            input("Dan duong dan thu muc SmartStay-Booking CU, roi Enter: ")
            .strip()
            .strip('"')
        )
    backend = project / "smartstay-backend" if project else args.backend
    frontend = project / "quickstay-frontend" if project else args.frontend
    if backend is None or frontend is None:
        parser.error("Can chi ro ca --backend va --frontend")
    try:
        result = apply_repair(
            Path(__file__).resolve().parent,
            backend,
            frontend,
            project=project,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit("KHONG CAP NHAT: " + str(exc)) from None
    print(
        "DA KIEM TRA" if args.dry_run else "DA CAP NHAT",
        result["files"],
        "tep backend/frontend.",
    )
    if result["backup"]:
        print("Sao luu ma cu:", result["backup"])
    print("Giu cac khoa/mat khau trong .env, .env.local va du lieu Docker dang co.")
    print("Tai backend cu: docker compose up -d --build backend")
    print("Tai frontend cu: npm ci, sau do npm run dev")
    print("Dang nhap lai sau khi cap nhat. Xem HUONG_DAN_SUA_5_LOI.md.")


if __name__ == "__main__":
    main()
