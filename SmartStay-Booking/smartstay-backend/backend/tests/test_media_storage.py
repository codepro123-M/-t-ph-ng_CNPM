import asyncio
import io
import threading
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from fastapi.testclient import TestClient

from app import main
from app.core import media_storage as media_module
from app.core.config import Settings
from app.core.media_storage import MediaStorage, MediaStorageError, create_s3_client


@pytest.fixture
def s3_config():
    return Settings(
        _env_file=None,
        MEDIA_BACKEND="s3",
        S3_ENDPOINT_URL="http://127.0.0.1:9000",
        S3_ACCESS_KEY="test-only-access-key",
        S3_SECRET_KEY="test-only-secret-key-not-for-use",
        S3_BUCKET="smartstay-test",
        S3_REGION="us-east-1",
        S3_HEALTH_CACHE_TTL_SECONDS=30,
    )


@pytest.fixture
def sdk(s3_config, monkeypatch):
    client = create_s3_client(s3_config)
    stub = Stubber(client)
    monkeypatch.setattr(media_module, "create_s3_client", lambda config: client)
    monkeypatch.setattr(media_module, "uuid4", lambda: SimpleNamespace(hex="a" * 32))
    with stub:
        yield client, stub
        stub.assert_no_pending_responses()
    client.close()


def queue_success(stub, config, *, version=None, content=None):
    payload = b"smartstay-storage-probe:" + b"a" * 32
    args = {"Bucket": config.S3_BUCKET, "Key": "_healthchecks/" + "a" * 32 + ".txt"}
    stub.add_response("head_bucket", {}, {"Bucket": config.S3_BUCKET})
    stub.add_response(
        "put_object",
        {"VersionId": version} if version else {},
        args | {"Body": payload, "ContentType": "text/plain"},
    )
    if version:
        args = args | {"VersionId": version}
    body = io.BytesIO(payload if content is None else content)
    stub.add_response(
        "get_object", {"Body": StreamingBody(body, len(body.getvalue()))}, args
    )
    stub.add_response("delete_object", {}, args)
    return body


@pytest.mark.asyncio
async def test_s3_write_read_cleanup_and_success_cache(s3_config, sdk):
    _, stub = sdk
    body = queue_success(stub, s3_config)
    storage = MediaStorage(s3_config)
    assert await storage.check_backend_health(force=True)
    assert body.closed
    # No additional requests are queued: the second check must use the cache.
    assert await storage.check_backend_health()


@pytest.mark.asyncio
async def test_s3_versioned_probe_deletes_the_exact_version(s3_config, sdk):
    queue_success(sdk[1], s3_config, version="probe-version-1")
    assert await MediaStorage(s3_config).check_backend_health(force=True)


@pytest.mark.asyncio
async def test_content_mismatch_still_cleans_up(s3_config, sdk):
    body = queue_success(sdk[1], s3_config, content=b"corrupted")
    with pytest.raises(MediaStorageError, match="content mismatch"):
        await MediaStorage(s3_config).check_backend_health(force=True)
    assert body.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,status",
    [("NoSuchBucket", 404), ("AccessDenied", 403), ("InvalidAccessKeyId", 403)],
)
async def test_s3_rejects_missing_bucket_or_bad_credentials(
    s3_config, sdk, code, status
):
    sdk[1].add_client_error(
        "head_bucket",
        code,
        "sensitive-error-text",
        status,
        expected_params={"Bucket": s3_config.S3_BUCKET},
    )
    with pytest.raises(MediaStorageError, match=code) as error:
        await MediaStorage(s3_config).check_backend_health(force=True)
    assert "sensitive-error-text" not in str(error.value)
    assert s3_config.S3_SECRET_KEY not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["put_object", "get_object", "delete_object"])
async def test_s3_requires_write_read_and_delete_permissions(s3_config, sdk, operation):
    _, stub = sdk
    args = {"Bucket": s3_config.S3_BUCKET, "Key": "_healthchecks/" + "a" * 32 + ".txt"}
    put_args = args | {
        "Body": b"smartstay-storage-probe:" + b"a" * 32,
        "ContentType": "text/plain",
    }
    stub.add_response("head_bucket", {}, {"Bucket": s3_config.S3_BUCKET})
    if operation == "put_object":
        stub.add_client_error(
            "put_object", "AccessDenied", http_status_code=403, expected_params=put_args
        )
        stub.add_response("delete_object", {}, args)
    else:
        stub.add_response("put_object", {}, put_args)
        if operation == "get_object":
            stub.add_client_error(
                "get_object", "AccessDenied", http_status_code=403, expected_params=args
            )
            stub.add_response("delete_object", {}, args)
        else:
            payload = put_args["Body"]
            stub.add_response(
                "get_object",
                {"Body": StreamingBody(io.BytesIO(payload), len(payload))},
                args,
            )
            stub.add_client_error(
                "delete_object",
                "AccessDenied",
                http_status_code=403,
                expected_params=args,
            )
    with pytest.raises(MediaStorageError, match="AccessDenied"):
        await MediaStorage(s3_config).check_backend_health(force=True)


@pytest.mark.asyncio
async def test_force_refresh_detects_failure_and_then_recovers(s3_config, sdk):
    _, stub = sdk
    queue_success(stub, s3_config)
    stub.add_client_error(
        "head_bucket",
        "AccessDenied",
        http_status_code=403,
        expected_params={"Bucket": s3_config.S3_BUCKET},
    )
    queue_success(stub, s3_config)
    storage = MediaStorage(s3_config)
    assert await storage.check_backend_health()
    with pytest.raises(MediaStorageError):
        await storage.check_backend_health(force=True)
    with pytest.raises(MediaStorageError):
        await (
            storage.check_backend_health()
        )  # Error cache must not report stale success.
    assert await storage.check_backend_health(force=True)


@pytest.mark.asyncio
async def test_sync_sdk_runs_outside_event_loop(s3_config, monkeypatch):
    storage = MediaStorage(s3_config)
    main_thread = threading.get_ident()
    observed = []
    monkeypatch.setattr(
        storage, "_probe_s3", lambda: observed.append(threading.get_ident())
    )
    assert await storage.check_backend_health(force=True)
    assert observed[0] != main_thread


@pytest.mark.asyncio
async def test_concurrent_checks_share_one_probe(s3_config, monkeypatch):
    storage = MediaStorage(s3_config)
    observed = []
    monkeypatch.setattr(storage, "_probe_s3", lambda: observed.append(True))
    assert all(
        await asyncio.gather(*(storage.check_backend_health() for _ in range(5)))
    )
    assert len(observed) == 1


@pytest.mark.asyncio
async def test_local_storage_does_not_create_s3_client(monkeypatch):
    storage = MediaStorage(Settings(_env_file=None, MEDIA_BACKEND="local"))
    monkeypatch.setattr(
        media_module,
        "create_s3_client",
        lambda config: pytest.fail("Unexpected S3 call"),
    )
    assert await storage.check_backend_health()


def test_sdk_has_timeouts_explicit_credentials_and_path_style(s3_config):
    with closing(create_s3_client(s3_config)) as client:
        config = client.meta.config
        assert config.connect_timeout == 2
        assert config.read_timeout == 2
        assert config.retries["total_max_attempts"] == 1
        assert config.s3["addressing_style"] == "path"
        assert config.signature_version == "s3v4"


def test_startup_fails_when_media_check_raises(services, monkeypatch):
    check = AsyncMock(side_effect=MediaStorageError("S3 storage unavailable"))
    monkeypatch.setattr(main.media_storage, "check_backend_health", check)
    with pytest.raises(MediaStorageError, match="unavailable"):
        with TestClient(main.create_app()):
            pass
    check.assert_awaited_once_with(force=True)
    services.close.assert_awaited_once()


def test_startup_fails_when_media_check_returns_false(services, monkeypatch):
    monkeypatch.setattr(
        main.media_storage, "check_backend_health", AsyncMock(return_value=False)
    )
    with pytest.raises(RuntimeError, match="returned false"):
        with TestClient(main.create_app()):
            pass
    services.close.assert_awaited_once()


def test_readiness_reports_media_failure_and_recovery(client, monkeypatch):
    check = AsyncMock(side_effect=[MediaStorageError("S3 unavailable"), True])
    monkeypatch.setattr(main.media_storage, "check_backend_health", check)
    failed = client.get("/health/ready")
    assert failed.status_code == 503
    assert failed.json()["media_ready"] is False
    recovered = client.get("/health/ready")
    assert recovered.status_code == 200
    assert recovered.json()["media_ready"] is True
