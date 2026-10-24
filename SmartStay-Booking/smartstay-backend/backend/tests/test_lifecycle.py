import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.database import close_db, db_manager


def test_startup_creates_unique_username_index(client, services):
    assert services.users.index_information()["auth_username_unique"]["unique"] is True
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["mounted_routers"] == 12


def test_readiness_fails_when_redis_is_unavailable(client, services):
    services.redis.ping.return_value = False
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_failed_startup_closes_open_connections(services, monkeypatch):
    monkeypatch.setattr(
        main, "ensure_auth_indexes", AsyncMock(side_effect=RuntimeError("index failed"))
    )
    with pytest.raises(RuntimeError, match="index failed"):
        with TestClient(main.create_app()):
            pass
    services.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_shutdown_cancels_and_awaits_worker(monkeypatch):
    worker = asyncio.create_task(asyncio.sleep(3600))
    redis = SimpleNamespace(aclose=AsyncMock())
    mongo = SimpleNamespace(close=Mock())
    monkeypatch.setattr(db_manager, "_readiness_task", worker)
    monkeypatch.setattr(db_manager, "redis", redis)
    monkeypatch.setattr(db_manager, "client", mongo)
    monkeypatch.setattr(db_manager, "db", object())
    monkeypatch.setattr(db_manager, "transaction_ready", True)
    await close_db()
    assert worker.cancelled()
    redis.aclose.assert_awaited_once()
    mongo.close.assert_called_once()
    assert db_manager._readiness_task is None
    assert db_manager.redis is None
    assert db_manager.client is None
    assert db_manager.db is None
    assert db_manager.transaction_ready is False
    await close_db()
    redis.aclose.assert_awaited_once()
