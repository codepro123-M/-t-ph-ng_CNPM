"""Regenerate the update manifest after intentional, reviewed source changes."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

IGNORED = {
    ".git",
    ".venv",
    ".venv-1",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "runtime_data",
    "dev-certs",
    "booking-backups",
    "repair-backups",
}


def eligible(path, root):
    relative = path.relative_to(root)
    if any(part in IGNORED for part in relative.parts):
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    if path.is_symlink():
        raise ValueError("Source must not contain symlinks: " + str(relative))
    return path.is_file()


def record(path, root):
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def generate(root):
    root = Path(root).resolve()
    result = {"version": "repair-2026-10-25-translation429"}
    for section, folder in (
        ("files", "smartstay-backend"),
        ("frontend_files", "quickstay-frontend"),
    ):
        base = root / folder
        result[section] = [
            record(path, base)
            for path in sorted(base.rglob("*"))
            if eligible(path, base)
        ]
    roots = [
        p
        for p in root.iterdir()
        if p.suffix in {".py", ".md"} or p.name in {".gitignore", ".gitattributes"}
    ]
    for folder in (root / "tests", root / ".github"):
        roots.extend(folder.rglob("*") if folder.exists() else [])
    result["root_files"] = [
        record(path, root) for path in sorted(set(roots)) if eligible(path, root)
    ]
    descriptor, temporary = tempfile.mkstemp(
        prefix="manifest-", suffix=".json", dir=root
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, root / "UPDATE_MANIFEST.json")
    finally:
        Path(temporary).unlink(missing_ok=True)
    return sum(
        len(result[section]) for section in ("files", "frontend_files", "root_files")
    )


if __name__ == "__main__":
    print("Da tao manifest cho", generate(Path(__file__).resolve().parent), "tep.")
