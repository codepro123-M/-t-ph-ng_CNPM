import asyncio
import logging
from contextlib import suppress
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger("smartstay.database")


class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    redis: Optional[aioredis.Redis] = None
    transaction_ready: bool = False
    _readiness_task: Optional[asyncio.Task] = None


db_manager = DatabaseManager()


async def connect_db() -> None:
    logger.info("Connecting to MongoDB...")
    db_manager.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=5000,
    )
    db_manager.db = db_manager.client[settings.MONGODB_DB_NAME]
    await db_manager.client.admin.command("ping")
    logger.info("MongoDB connected to database '%s'.", settings.MONGODB_DB_NAME)

    logger.info("Connecting to Redis...")
    db_manager.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await db_manager.redis.ping()
    logger.info("Redis connected successfully.")


async def assert_transaction_capability() -> None:
    if db_manager.client is None:
        raise RuntimeError("MongoDB client is not initialized.")

    hello_info = await db_manager.client.admin.command("hello")
    if "setName" not in hello_info and hello_info.get("msg") != "isdbgrid":
        raise RuntimeError(
            "MongoDB Transaction Capability Error: MongoDB must run as a Replica Set."
        )

    async with await db_manager.client.start_session() as session:
        async with session.start_transaction():
            await db_manager.db["_tx_probe"].update_one(
                {"_id": "startup_probe"},
                {"$set": {"ok": True}},
                upsert=True,
                session=session,
            )

    db_manager.transaction_ready = True
    logger.info("MongoDB transaction capability verified (Replica Set active).")


async def refresh_transaction_readiness() -> bool:
    try:
        if db_manager.client is None:
            db_manager.transaction_ready = False
            return False
        hello_info = await db_manager.client.admin.command("hello")
        db_manager.transaction_ready = bool(
            "setName" in hello_info or hello_info.get("msg") == "isdbgrid"
        )
        return db_manager.transaction_ready
    except Exception as exc:
        logger.warning("Transaction readiness check failed: %s", exc)
        db_manager.transaction_ready = False
        return False


async def _transaction_readiness_loop(interval_seconds: int = 30) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        await refresh_transaction_readiness()


def start_transaction_readiness_loop() -> None:
    if db_manager._readiness_task is None or db_manager._readiness_task.done():
        db_manager._readiness_task = asyncio.create_task(_transaction_readiness_loop())


async def close_db() -> None:
    if db_manager._readiness_task is not None:
        if not db_manager._readiness_task.done():
            db_manager._readiness_task.cancel()
        with suppress(asyncio.CancelledError):
            await db_manager._readiness_task
        db_manager._readiness_task = None
    if db_manager.redis is not None:
        await db_manager.redis.aclose()
        db_manager.redis = None
    if db_manager.client is not None:
        db_manager.client.close()
        db_manager.client = None
    db_manager.db = None
    db_manager.transaction_ready = False


def get_db() -> AsyncIOMotorDatabase:
    if db_manager.db is None:
        raise RuntimeError("Database is not initialized.")
    return db_manager.db


def get_redis() -> aioredis.Redis:
    if db_manager.redis is None:
        raise RuntimeError("Redis is not initialized.")
    return db_manager.redis
