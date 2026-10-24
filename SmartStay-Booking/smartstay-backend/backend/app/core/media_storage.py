"""S3 readiness checks use a unique temporary object and bounded SDK timeouts."""

import asyncio
import logging
from contextlib import closing
from time import monotonic
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, settings

logger = logging.getLogger("smartstay.media")


class MediaStorageError(RuntimeError):
    """A safe-to-display storage readiness error; never includes credentials."""


def describe_s3_error(exc: Exception) -> str:
    if isinstance(exc, MediaStorageError):
        return str(exc)
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        allowed = {
            "AccessDenied",
            "InvalidAccessKeyId",
            "SignatureDoesNotMatch",
            "NoSuchBucket",
            "NoSuchKey",
            "ExpiredToken",
            "InvalidToken",
            "AuthorizationHeaderMalformed",
            "PermanentRedirect",
            "404",
            "403",
        }
        reason = code if code in allowed else "S3 request rejected"
    else:
        reason = type(exc).__name__
    return f"S3 media readiness failed ({reason})."


def create_s3_client(config: Settings):
    config.validate_media_storage()
    return boto3.session.Session().client(
        "s3",
        endpoint_url=config.S3_ENDPOINT_URL or None,
        region_name=config.S3_REGION,
        aws_access_key_id=config.S3_ACCESS_KEY,
        aws_secret_access_key=config.S3_SECRET_KEY,
        aws_session_token=config.S3_SESSION_TOKEN or None,
        verify=config.S3_CA_BUNDLE or True,
        config=Config(
            signature_version="s3v4",
            connect_timeout=config.S3_CONNECT_TIMEOUT_SECONDS,
            read_timeout=config.S3_READ_TIMEOUT_SECONDS,
            retries={"total_max_attempts": 1, "mode": "standard"},
            s3={"addressing_style": config.S3_ADDRESSING_STYLE},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


class MediaStorage:
    def __init__(self, config: Settings | None = None):
        self.config = config if config is not None else settings
        self._lock = asyncio.Lock()
        self._cache_until = 0.0
        self._last_error: str | None = None

    async def check_backend_health(self, *, force: bool = False) -> bool:
        self.config.validate_media_storage()
        if self.config.MEDIA_BACKEND.strip().lower() == "local":
            return True
        async with self._lock:
            if not force and monotonic() < self._cache_until:
                if self._last_error:
                    raise MediaStorageError(self._last_error)
                return True
            try:
                # boto3 is synchronous; keep its network IO off the async loop.
                await run_in_threadpool(self._probe_s3)
            except Exception as exc:
                self._last_error = describe_s3_error(exc)
                self._cache_until = monotonic() + min(
                    2, self.config.S3_HEALTH_CACHE_TTL_SECONDS
                )
                logger.warning("%s", self._last_error)
                raise MediaStorageError(self._last_error) from None
            self._last_error = None
            self._cache_until = monotonic() + self.config.S3_HEALTH_CACHE_TTL_SECONDS
            logger.info(
                "S3 media readiness OK: bucket access, write, read and cleanup verified."
            )
            return True

    def _probe_s3(self) -> None:
        key = f"{self.config.S3_HEALTH_PREFIX.strip('/')}/{uuid4().hex}.txt"
        payload = b"smartstay-storage-probe:" + uuid4().hex.encode("ascii")
        with closing(create_s3_client(self.config)) as client:
            client.head_bucket(Bucket=self.config.S3_BUCKET)
            object_args = {"Bucket": self.config.S3_BUCKET, "Key": key}
            cleanup_args = dict(object_args)
            problem = None
            try:
                result = client.put_object(
                    **object_args, Body=payload, ContentType="text/plain"
                )
                # Remove the exact probe version when bucket versioning is on.
                if result.get("VersionId"):
                    object_args["VersionId"] = result["VersionId"]
                    cleanup_args["VersionId"] = result["VersionId"]
                response = client.get_object(**object_args)
                with closing(response["Body"]) as stream:
                    if stream.read(len(payload) + 1) != payload:
                        raise MediaStorageError(
                            "S3 media readiness failed (probe content mismatch)."
                        )
            except Exception as exc:
                problem = exc
            finally:
                # Also attempt cleanup after an ambiguous PUT timeout.
                try:
                    client.delete_object(**cleanup_args)
                except Exception as cleanup_exc:
                    logger.warning(
                        "S3 probe cleanup failed (%s).", type(cleanup_exc).__name__
                    )
                    if problem is None:
                        problem = cleanup_exc
            if problem is not None:
                raise MediaStorageError(describe_s3_error(problem)) from None


media_storage = MediaStorage()
