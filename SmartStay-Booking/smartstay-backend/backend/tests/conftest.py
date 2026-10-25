"""Unit tests isolate services; integration tests also run on a real replica set."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis.aioredis
import mongomock
import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.database import db_manager


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def sort(self, *args):
        self.cursor = self.cursor.sort(*args)
        return self

    def limit(self, count):
        self.cursor = self.cursor.limit(count)
        return self

    def skip(self, count):
        self.cursor = self.cursor.skip(count)
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.cursor)
        except StopIteration:
            raise StopAsyncIteration from None

    async def to_list(self, length=None):
        return list(self.cursor)[:length]


class Collection:
    def __init__(self, collection):
        self.collection = collection

    def find(self, *args, **kwargs):
        kwargs.pop("session", None)
        return Cursor(self.collection.find(*args, **kwargs))

    def aggregate(self, *args, **kwargs):
        from pymongo.errors import OperationFailure

        kwargs.pop("session", None)
        kwargs.pop("maxTimeMS", None)
        if args[0] and "$geoNear" in args[0][0]:
            raise OperationFailure("Unit storage has no geospatial index", code=27)
        return Cursor(self.collection.aggregate(*args, **kwargs))

    def __getattr__(self, name):
        async def call(*args, **kwargs):
            kwargs.pop("session", None)
            return getattr(self.collection, name)(*args, **kwargs)

        return call


class Database:
    def __init__(self):
        self.raw = mongomock.MongoClient(tz_aware=True).db

    def __getitem__(self, name):
        return Collection(self.raw[name])


class Session:
    def __init__(self, db):
        self.db = db
        self.snapshot = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if self.snapshot is not None and exc:
            for name in self.db.raw.list_collection_names():
                self.db.raw[name].delete_many({})
            for name, documents in self.snapshot.items():
                if documents:
                    self.db.raw[name].insert_many(documents)
        self.snapshot = None

    def start_transaction(self, **kwargs):
        self.snapshot = {
            name: deepcopy(list(self.db.raw[name].find()))
            for name in self.db.raw.list_collection_names()
        }
        return self

    async def with_transaction(self, callback, **kwargs):
        async with self.start_transaction():
            return await callback(self)


@pytest.fixture
def services(monkeypatch, tmp_path):
    async def parked_worker():
        await asyncio.Event().wait()

    monkeypatch.setattr(main.audio_task_manager, "worker_loop", parked_worker)
    db = Database()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis.ping = AsyncMock(return_value=True)
    mongo_client = SimpleNamespace(
        admin=SimpleNamespace(command=AsyncMock(return_value={"ok": 1})),
        start_session=AsyncMock(side_effect=lambda *args, **kwargs: Session(db)),
    )
    monkeypatch.setattr(db_manager, "db", db)
    monkeypatch.setattr(db_manager, "client", mongo_client)
    monkeypatch.setattr(db_manager, "redis", redis)
    monkeypatch.setattr(main.settings, "APP_ENV", "test")
    monkeypatch.setattr(main.settings, "SUPERADMIN_BOOTSTRAP_MODE", "disabled")
    monkeypatch.setattr(main.settings, "MEDIA_BACKEND", "local")
    monkeypatch.setattr(main.settings, "JWT_SECRET", "test-access-only-key-" * 4)
    monkeypatch.setattr(
        main.settings, "REFRESH_TOKEN_SECRET", "test-refresh-only-key-" * 4
    )
    monkeypatch.setattr(main.settings, "SECRET_KEY", "test-fernet-only-key-" * 4)
    monkeypatch.setattr(main.settings, "CONTENT_MEDIA_DIR", tmp_path / "content-media")
    monkeypatch.setattr(main, "connect_db", AsyncMock())
    monkeypatch.setattr(main, "assert_transaction_capability", AsyncMock())
    monkeypatch.setattr(
        main, "refresh_transaction_readiness", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(main, "start_transaction_readiness_loop", lambda: None)
    close = AsyncMock()
    monkeypatch.setattr(main, "close_db", close)
    return SimpleNamespace(db=db, users=db.raw.auth_users, redis=redis, close=close)


@pytest.fixture
def client(services):
    with TestClient(
        main.create_app(), base_url="https://localhost:8443"
    ) as test_client:
        yield test_client


@pytest.fixture
def root(client, services):
    import bcrypt
    from test_phase2 import ROOT_PASSWORD, admin_login

    services.db.raw.admin_users.insert_one(
        {
            "username": "superadmin",
            "full_name": "Root",
            "role": "super_admin",
            "password_hash": bcrypt.hashpw(
                ROOT_PASSWORD.encode(), bcrypt.gensalt()
            ).decode(),
            "is_active": True,
            "auth_version": 1,
        }
    )
    return admin_login(client)["access_token"]
