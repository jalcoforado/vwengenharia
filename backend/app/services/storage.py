from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


class StorageService:
    def __init__(self) -> None:
        common = {
            "service_name": "s3",
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        }
        self.internal = boto3.client(endpoint_url=settings.s3_endpoint, **common)
        self.public = boto3.client(endpoint_url=settings.s3_public_endpoint, **common)

    def presign_put(self, *, object_key: str, content_type: str) -> str:
        return self.public.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=settings.s3_presign_seconds,
        )

    def object_metadata(self, *, object_key: str) -> dict | None:
        try:
            return self.internal.head_object(
                Bucket=settings.s3_bucket,
                Key=object_key,
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise


@lru_cache
def get_storage() -> StorageService:
    return StorageService()
