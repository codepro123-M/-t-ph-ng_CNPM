"""Remove expired identity ciphertext without deleting the owner's account."""

import asyncio
import logging
from contextlib import suppress

from app.core.audit import audit, transaction
from app.core.config import settings
from app.core.database import get_db
from app.core.security import utcnow

logger = logging.getLogger("smartstay.retention")


async def purge_expired_pii():
    db = get_db()
    query = {
        "pii_expires_at": {"$lte": utcnow()},
        "national_id_encrypted": {"$exists": True},
    }
    count = 0
    async for user in db["admin_users"].find(query, {"_id": 1}).limit(500):
        async with transaction() as session:
            changed = await db["admin_users"].update_one(
                {"_id": user["_id"]} | query,
                {
                    "$unset": {"national_id_encrypted": ""},
                    "$set": {"pii_purged_at": utcnow()},
                },
                session=session,
            )
            if changed.modified_count:
                await audit("pii.purge", "admin_users", user["_id"], session=session)
                count += 1
    return count


async def retention_loop():
    while True:
        await asyncio.sleep(settings.PII_CLEANUP_INTERVAL_SECONDS)
        try:
            while await purge_expired_pii() == 500:
                await asyncio.sleep(0)
        except Exception:
            logger.error("PII cleanup failed; will retry on the next interval.")


async def stop_retention(task):
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
