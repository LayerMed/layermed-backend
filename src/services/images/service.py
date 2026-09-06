import io
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile

from src.services.images.exceptions import ImageExtensionError, ImageWeightError
from src.common.utils import mb_to_bytes


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


def avatar_validate(image: UploadFile) -> None:
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
    