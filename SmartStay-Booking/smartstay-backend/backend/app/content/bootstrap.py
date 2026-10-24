from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.core.database import get_db
from app.core.security import utcnow


async def ensure_content_indexes():
    db = get_db()
    root = Path(settings.CONTENT_MEDIA_DIR)
    if settings.APP_ENV.lower() in {"dev", "development", "test"}:
        root.mkdir(parents=True, exist_ok=True)
    elif not root.is_dir():
        raise RuntimeError(
            "CONTENT_MEDIA_DIR must exist in non-development environments"
        )
    await db["pois"].create_index(
        [("location", "2dsphere")], name="poi_location_2dsphere"
    )
    await db["pois"].create_index([("owner_id", 1), ("_id", 1)])
    await db["menu_items"].create_index([("poi_id", 1), ("_id", 1)])
    await db["poi_localizations"].create_index(
        [("poi_id", 1), ("language", 1)], unique=True
    )
    await db["poi_submissions"].create_index([("owner_id", 1), ("_id", -1)])
    await db["poi_submissions"].create_index([("poi_id", 1), ("status", 1)])
    await db["owner_notifications"].create_index(
        [("owner_id", 1), ("is_read", 1), ("_id", -1)]
    )
    await db["media_assets"].create_index([("owner_id", 1), ("state", 1)])
    await db["media_cleanup_jobs"].create_index("asset_id", unique=True)
    await db["media_cleanup_jobs"].create_index([("state", 1), ("run_after", 1)])
    await db["content_changes"].create_index([("poi_id", 1), ("version", -1)])
    await db["content_changes"].create_index("changed_at")
    await db["content_dataset_versions"].update_one(
        {"_id": "poi"},
        {
            "$setOnInsert": {
                "version": 0,
                "updated_at": utcnow(),
                "created_at": utcnow(),
                "schema_version": 1,
                "dataset_id": uuid4().hex,
            }
        },
        upsert=True,
    )
