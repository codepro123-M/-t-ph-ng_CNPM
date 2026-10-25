from pathlib import Path

from app.core.config import settings


def runtime_directories(config=None):
    config = config or settings
    return [
        config.STATIC_DIR / "audio",
        config.STATIC_DIR / "poi-images",
        config.MAP_PACK_DATA_DIR / "packs/current",
        config.MAP_PACK_DATA_DIR / "styles",
        config.MAP_PACK_DATA_DIR / "fonts",
        config.CONTENT_MEDIA_DIR,
    ]


def ensure_runtime_storage():
    if settings.APP_ENV.lower() in {"dev", "development", "test"}:
        for path in runtime_directories():
            path.mkdir(parents=True, exist_ok=True)


def verify_runtime_storage():
    ensure_runtime_storage()
    for path in runtime_directories():
        if not path.is_dir():
            raise RuntimeError(f"Runtime storage directory missing: {path}")


def resolve_safe_path(base, relative):
    root = Path(base).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Path traversal attempt blocked")
    return candidate
