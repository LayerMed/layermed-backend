# pyright: reportGeneralTypeIssues=false

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import aioboto3
from botocore.exceptions import ClientError
from types_aiobotocore_s3 import S3Client

from src.common.enums import S3Folders
from src.core.logs import logger
from src.core.config import settings

aioboto = aioboto3.Session()


@asynccontextmanager
async def get_s3_client() -> AsyncGenerator[S3Client, None]:
    async with aioboto.client(
        service_name="s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    ) as client:
        yield client


async def upload_image(
    file_bytes: bytes, folder: S3Folders, extension: str = "jpg"
) -> str:
    filename = f"{uuid.uuid4()}.{extension}"
    key = f"{folder}/{filename}"

    async with get_s3_client() as s3:
        await s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=file_bytes,
            ContentType=f"image/{extension}",
        )

    return key


async def delete_image(key: str | None) -> bool:
    if key is None:
        return False

    try:
        async with get_s3_client() as s3:
            await s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
            return True
    except ClientError as e:
        logger.warning("Error while deleting the file {key}: {e}", key=key, e=e)
        return False
