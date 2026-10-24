"""Explicit safe audit metadata; called inside the business transaction."""

from contextlib import asynccontextmanager
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from app.core.database import db_manager, get_db
from app.core.security import utcnow


@asynccontextmanager
async def transaction():
    async with await db_manager.client.start_session() as session:
        async with session.start_transaction():
            yield session


async def run_transaction(operation):
    """Retry MongoDB transient conflicts; callbacks must contain DB operations only."""
    async with await db_manager.client.start_session() as session:
        return await session.with_transaction(
            operation,
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
        )


@asynccontextmanager
async def read_snapshot():
    """One consistent view across aggregate/find without a write transaction."""
    async with await db_manager.client.start_session(
        snapshot=True, causal_consistency=False
    ) as session:
        yield session


async def audit(
    action, resource, resource_id, actor=None, *, session=None, details=None
):
    allowed = {"status", "role", "fields", "count", "reason", "realm"}
    safe = {k: v for k, v in (details or {}).items() if k in allowed}
    await get_db()["audit_logs"].insert_one(
        {
            "user_id": (actor or {}).get("sub", "system"),
            "user_realm": (actor or {}).get("realm", "system"),
            "action": action,
            "resource": resource,
            "resource_id": str(resource_id),
            "created_at": utcnow(),
            "details": safe,
        },
        session=session,
    )


def public_document(document):
    """Only use for records with no secrets (roles, rooms, posts, audit)."""
    return {
        ("id" if key == "_id" else key): (str(value) if key == "_id" else value)
        for key, value in document.items()
    }
