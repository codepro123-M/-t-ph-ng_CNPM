"""Apply this extracted update to an existing Smart Stay project, with code backup.

Run: python AP_DUNG_BAN_SUA.py --project "C:\\path\\smart-stay-concierge"
Without --project, a folder chooser opens. Only Python's standard library is used.
"""

import argparse
from datetime import datetime
import os
from pathlib import Path
import secrets
import shutil
import tempfile

ALLOWED_FOLDERS = {"backend", "scripts", "infra", ".github"}
IGNORED_FOLDERS = {
    ".git",
    ".venv",
    ".venv-1",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "runtime_data",
    "dev-certs",
    "static",
}
ALLOWED_FILES = {".gitignore", ".env.example", "pytest.ini", "AP_DUNG_BAN_SUA.py"}


def update_files(source):
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in IGNORED_FOLDERS for part in relative.parts):
            continue
        if path.name == ".env" or (
            path.name.startswith(".env.") and path.name != ".env.example"
        ):
            continue
        if path.is_symlink():
            raise ValueError("Update source must not contain symbolic links")
        if not path.is_file():
            continue
        if relative.parts[0] in ALLOWED_FOLDERS or (
            len(relative.parts) == 1
            and (
                relative.name in ALLOWED_FILES
                or relative.suffix == ".md"
                or relative.match("docker-compose*.yml")
            )
        ):
            yield path, relative


def apply_update(source, project, *, dry_run=False):
    source, project = Path(source).resolve(), Path(project).resolve()
    if source == project:
        raise ValueError(
            "Extract the ZIP into a separate folder before applying the update"
        )
    for root in (source, project):
        if (
            not (root / "backend/app/main.py").is_file()
            or not (root / "docker-compose.yml").is_file()
        ):
            raise ValueError(
                "Select the project folder containing backend and docker-compose.yml"
            )
    if not (source / "scripts/smoke_phase3.py").is_file():
        raise ValueError("Extract the complete update ZIP first")
    files = list(update_files(source))
    for _, relative in files:
        destination = project / relative
        if not destination.resolve().is_relative_to(project):
            raise ValueError("A destination path resolves outside the selected project")
        if destination.exists() and not destination.is_file():
            raise ValueError("A destination file conflicts with an existing directory")
    if dry_run:
        return {"files": len(files), "backup": None}
    backup = project.parent / (
        "smart-stay-code-backup-"
        + datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-"
        + secrets.token_hex(3)
    )
    backup.mkdir()
    existing = set()
    # Complete every backup before replacing the first file.
    for _, relative in files:
        destination = project / relative
        if destination.is_file():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
            existing.add(relative)
    applied = []
    try:
        for original, relative in files:
            destination = project / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix="smartstay-update-", dir=destination.parent
            )
            os.close(descriptor)
            try:
                shutil.copy2(original, temporary)
                os.replace(temporary, destination)
            finally:
                Path(temporary).unlink(missing_ok=True)
            applied.append(relative)
    except Exception:
        for relative in reversed(applied):
            destination = project / relative
            if relative in existing:
                shutil.copy2(backup / relative, destination)
            else:
                destination.unlink(missing_ok=True)
        raise
    return {"files": len(files), "backup": str(backup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    selected = args.project
    if not selected:
        try:
            import tkinter as tk
            from tkinter import filedialog

            window = tk.Tk()
            window.withdraw()
            selected = filedialog.askdirectory(
                title="Chon thu muc du an cu co backend va docker-compose.yml"
            )
            window.destroy()
        except Exception:
            raise SystemExit(
                "Use --project followed by the existing project folder path"
            ) from None
    if not selected:
        raise SystemExit("No folder selected; no files were changed")
    try:
        result = apply_update(
            Path(__file__).resolve().parent, selected, dry_run=args.dry_run
        )
    except Exception as exc:
        raise SystemExit("Update failed: " + str(exc)) from None
    print("DRY RUN" if args.dry_run else "UPDATE COMPLETE")
    print("Project:", Path(selected).resolve())
    print("Code files:", result["files"])
    if result["backup"]:
        print("Code backup:", result["backup"])
    print("Next, open the ORIGINAL project folder in VS Code and run:")
    print("docker compose up -d --build")
    print("docker compose ps -a")
    print("python scripts/smoke_phase3.py")


if __name__ == "__main__":
    main()
