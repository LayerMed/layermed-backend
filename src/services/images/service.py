import io
from collections.abc import Callable
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from src.common.enums import S3Folders
from src.services.images.exceptions import ImageExtensionError, ImageWeightError
from src.services.storage.s3 import upload_image


def mb_to_bytes(mb: float) -> int:
    return int(mb * 1024 * 1024)


def image_validate(image: UploadFile) -> None:
    if image.size is None or image.size > mb_to_bytes(5):
        raise ImageWeightError()

    permitted_mimes = ["image/jpeg", "image/png", "image/webp"]
    if image.content_type not in permitted_mimes:
        raise ImageExtensionError()

    if not image.filename:
        raise ImageExtensionError()

    permitted_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    if Path(image.filename).suffix.lower() not in permitted_extensions:
        raise ImageExtensionError()


def avatar_optimization(image_bytes: bytes, target_size: int = 400) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_bytes))

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        width, height = img.size

        min_side = min(width, height)
        left = (width - min_side) // 2
        top = (height - min_side) // 2
        right = (width + min_side) // 2
        bottom = (height + min_side) // 2

        img = img.crop((left, top, right, bottom))
        img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)

        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=85)

        return output_buffer.getvalue()
    except UnidentifiedImageError:
        raise ImageExtensionError()


def offer_optimization(image_bytes: bytes, max_width: int = 1200) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_bytes))

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=85)

        return output_buffer.getvalue()
    except UnidentifiedImageError:
        raise ImageExtensionError()


async def save_and_upload_image(
    image: UploadFile,
    folder: S3Folders,
    optimizer: Callable[[bytes], bytes],
) -> str:
    image_validate(image)
    image_bytes = await image.read()
    optimized_bytes = optimizer(image_bytes)
    return await upload_image(optimized_bytes, folder)
