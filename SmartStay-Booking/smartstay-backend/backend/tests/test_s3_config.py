import pytest

from app.core.config import Settings


BASE = {
    "MEDIA_BACKEND": "s3",
    "S3_BUCKET": "smartstay-test",
    "S3_ACCESS_KEY": "test-access",
    "S3_SECRET_KEY": "test-secret",
    "S3_ENDPOINT_URL": "http://s3:9000",
}


@pytest.mark.parametrize(
    "field", ["S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_REGION"]
)
def test_s3_requires_configuration(field):
    with pytest.raises(RuntimeError, match=field):
        Settings(_env_file=None, **(BASE | {field: ""})).validate_media_storage()


@pytest.mark.parametrize(
    "endpoint",
    [
        "ftp://example.org",
        "http://user:password@s3:9000",
        "http://s3?secret=value",
        "http://s3#secret",
        "http://s3:invalid",
        " http://s3:9000",
    ],
)
def test_invalid_endpoint_is_rejected_without_echoing_it(endpoint):
    with pytest.raises(RuntimeError, match="S3_ENDPOINT_URL") as exc:
        Settings(
            _env_file=None, **(BASE | {"S3_ENDPOINT_URL": endpoint})
        ).validate_media_storage()
    assert endpoint not in str(exc.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"S3_BUCKET": "INVALID"},
        {"S3_BUCKET": "a..b"},
        {"S3_HEALTH_PREFIX": "../media"},
        {"S3_ADDRESSING_STYLE": "typo"},
        {"MEDIA_BACKEND": "typo"},
    ],
)
def test_invalid_s3_options_are_rejected(changes):
    with pytest.raises(RuntimeError):
        Settings(_env_file=None, **(BASE | changes)).validate_media_storage()


def test_native_aws_endpoint_is_optional():
    Settings(
        _env_file=None, **(BASE | {"S3_ENDPOINT_URL": ""})
    ).validate_media_storage()
