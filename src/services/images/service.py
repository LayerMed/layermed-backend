import io
from collections.abc import Callable
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError

from src.common.enums import S3Folders
from src.services.images.exceptions import (
    ImageDimensionsError,
    ImageExtensionError,
    ImageWeightError,
    MegabyteNotLessNull,
)
from src.services.storage.s3 import upload_image

Image.MAX_IMAGE_PIXELS = 16_000_000


def mb_to_bytes(mb: float) -> int:
    if mb < 0:
        raise MegabyteNotLessNull
    return int(mb * 1024 * 1024)


def image_validate(image: UploadFile) -> None:
    if image.size is not None and image.size > mb_to_bytes(5):
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
        with Image.open(io.BytesIO(image_bytes)) as img:
            if img.width > 5000 or img.height > 5000:
                raise ImageDimensionsError()

            if img.mode in ("RGBA", "P", "L"):
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

    except DecompressionBombError:
        raise ImageDimensionsError()
    except (UnidentifiedImageError, OSError):
        raise ImageExtensionError()


def offer_optimization(image_bytes: bytes, max_width: int = 1200) -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            if img.width > 6000 or img.height > 6000:
                raise ImageDimensionsError()

            if img.mode in ("RGBA", "P", "L"):
                img = img.convert("RGB")

            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG", quality=85)
            return output_buffer.getvalue()

    except DecompressionBombError:
        raise ImageDimensionsError()
    except (UnidentifiedImageError, OSError):
        raise ImageExtensionError()


async def save_and_upload_image(
    image: UploadFile,
    folder: S3Folders,
    optimizer: Callable[[bytes], bytes],
) -> str:
    image_validate(image)

    max_size = mb_to_bytes(5)
    image_bytes = await image.read(max_size + 1)
    if len(image_bytes) > max_size:
        raise ImageWeightError()

    optimized_bytes = optimizer(image_bytes)
    return await upload_image(optimized_bytes, folder)
