"""Initialize the local development S3 bucket; never runs during backend startup."""

from contextlib import closing

from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.media_storage import create_s3_client, describe_s3_error


def main():
    if settings.APP_ENV.strip().lower() not in {"dev", "development", "test"}:
        raise SystemExit(
            "S3 bucket initialization is only enabled for local development/test."
        )
    if settings.MEDIA_BACKEND.strip().lower() != "s3":
        raise SystemExit("Set MEDIA_BACKEND=s3 before initializing the bucket.")
    settings.validate_media_storage()
    try:
        with closing(create_s3_client(settings)) as client:
            try:
                client.head_bucket(Bucket=settings.S3_BUCKET)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code not in {"404", "NoSuchBucket", "NotFound"}:
                    raise
                args = {"Bucket": settings.S3_BUCKET}
                if settings.S3_REGION != "us-east-1":
                    args["CreateBucketConfiguration"] = {
                        "LocationConstraint": settings.S3_REGION
                    }
                client.create_bucket(**args)
        print("Local S3 bucket is ready.")
    except Exception as exc:
        raise SystemExit(describe_s3_error(exc)) from None


if __name__ == "__main__":
    main()
