from pathlib import Path
from app.core.config import settings

REQUIRED_RUNTIME_DIRS = [
    settings.STATIC_DIR / "audio",
    settings.STATIC_DIR / "poi-images",
    settings.MAP_PACK_DATA_DIR / "packs" / "current",
    settings.MAP_PACK_DATA_DIR / "styles",
    settings.MAP_PACK_DATA_DIR / "fonts",
]


def ensure_runtime_storage() -> None:
    for directory in REQUIRED_RUNTIME_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


def verify_runtime_storage() -> None:
    ensure_runtime_storage()
    for directory in REQUIRED_RUNTIME_DIRS:
        if not directory.exists() or not directory.is_dir():
            raise RuntimeError(f"Runtime storage directory missing: {directory}")


def resolve_safe_path(base: Path, relative: str) -> Path:
    base_resolved = base.resolve()
    target_resolved = (base_resolved / relative.lstrip("/\\")).resolve()
    if not target_resolved.is_relative_to(base_resolved):
        raise ValueError(f"Path traversal attempt blocked: {relative}")
    return target_resolved
