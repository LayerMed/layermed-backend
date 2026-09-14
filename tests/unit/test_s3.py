from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import ClientError

from src.common.enums import S3Folders
from src.services.storage import s3 as s3_service


def use_client(monkeypatch: pytest.MonkeyPatch, client: AsyncMock) -> None:
    @asynccontextmanager
    async def fake_get_s3_client():
        yield client

    monkeypatch.setattr(s3_service, "get_s3_client", fake_get_s3_client)


async def test_upload_image_sends_expected_object_and_returns_generated_key(
    monkeypatch: pytest.MonkeyPatch,
):
    client = AsyncMock()
    use_client(monkeypatch, client)

    key = await s3_service.upload_image(b"image-bytes", S3Folders.DOCTORS)

    assert key.startswith("doctors/")
    assert key.endswith(".jpg")
    client.put_object.assert_awaited_once_with(
        Bucket=s3_service.settings.S3_BUCKET_NAME,
        Key=key,
        Body=b"image-bytes",
        ContentType="image/jpg",
    )


async def test_delete_image_with_none_does_not_call_s3(
    monkeypatch: pytest.MonkeyPatch,
):
    client = AsyncMock()
    use_client(monkeypatch, client)

    assert await s3_service.delete_image(None) is False
    client.delete_object.assert_not_awaited()


async def test_delete_image_returns_true_after_success(monkeypatch: pytest.MonkeyPatch):
    client = AsyncMock()
    use_client(monkeypatch, client)

    assert await s3_service.delete_image("doctors/avatar.jpg") is True
    client.delete_object.assert_awaited_once_with(
        Bucket=s3_service.settings.S3_BUCKET_NAME,
        Key="doctors/avatar.jpg",
    )


async def test_delete_image_converts_s3_client_error_to_false(
    monkeypatch: pytest.MonkeyPatch,
):
    client = AsyncMock()
    client.delete_object.side_effect = ClientError(
        {"Error": {"Code": "InternalError", "Message": "failed"}},
        "DeleteObject",
    )
    use_client(monkeypatch, client)

    assert await s3_service.delete_image("offers/image.jpg") is False
