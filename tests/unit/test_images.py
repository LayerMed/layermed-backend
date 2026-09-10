import io

import pytest
from fastapi import UploadFile
from PIL import Image

from src.services.images.exceptions import (
    ImageExtensionError,
    ImageWeightError,
    MegabyteNotLessNull,
)
from src.services.images.service import (
    avatar_optimization,
    image_validate,
    mb_to_bytes,
    offer_optimization,
)


class TestMbToBytes:
    @pytest.mark.parametrize(
        "mb, result",
        [
            (1, 1024 * 1024),
            (10, 10 * 1024 * 1024),
            (10.5, int(10.5 * 1024 * 1024)),
            (0, 0),
        ],
    )
    def test_mb_to_bytes(self, mb: float, result: int):
        assert mb_to_bytes(mb) == result

    def test_error_mb_to_bytes(self):
        with pytest.raises(MegabyteNotLessNull):
            mb_to_bytes(-10)


class TestImageValidate:
    content = io.BytesIO(b"Image")

    def test_image_validate(self):
        good_file = UploadFile(
            file=self.content,
            filename="avatar.jpg",
            headers={"content-type": "image/jpeg"},
        )
        good_file.size = 1024

        assert image_validate(good_file) is None

    def test_size_image_validate(self):
        bad_file = UploadFile(
            file=self.content,
            filename="avatar.jpg",
            headers={"content-type": "image/jpeg"},
        )
        bad_file.size = mb_to_bytes(100)

        with pytest.raises(ImageWeightError):
            image_validate(bad_file)

    extensions = ["exe", "EXE", "ini", "INI", "com", "msi", "bat"]

    @pytest.mark.parametrize("mime", extensions)
    def test_mimes_image_validate(self, mime: str):
        bad_file = UploadFile(
            file=self.content,
            filename="avatar.jpg",
            headers={"content-type": f"image/{mime}"},
        )
        bad_file.size = 1024

        with pytest.raises(ImageExtensionError):
            image_validate(bad_file)

    @pytest.mark.parametrize("extension", extensions)
    def test__image_validate(self, extension: str):
        bad_file = UploadFile(
            file=self.content,
            filename=f"avatar.{extension}",
            headers={"content-type": "image/png"},
        )
        bad_file.size = 1024

        with pytest.raises(ImageExtensionError):
            image_validate(bad_file)


class TestOfferValidate:
    def generate_image_bytes(
        self, size: tuple[int, int], mode: str, image_format: str
    ) -> bytes:
        img = Image.new(mode, size, color="blue")
        buffer = io.BytesIO()
        img.save(buffer, format=image_format)
        return buffer.getvalue()

    @pytest.mark.parametrize(
        "w, h, mode, image_format",
        [
            (200, 200, "RGB", "JPEG"),
            (1920, 1080, "RGB", "JPEG"),
            (600, 1200, "RGBA", "PNG"),
            (100, 100, "P", "PNG"),
            (1, 1, "L", "PNG"),
        ],
    )
    def test_avatar_optimisation(self, w: int, h: int, mode: str, image_format: str):
        raw_bytes = self.generate_image_bytes((w, h), mode, image_format)
        avatar_bytes = avatar_optimization(raw_bytes)

        result_image = Image.open(io.BytesIO(avatar_bytes))

        assert result_image.size == (400, 400)
        assert result_image.format == "JPEG"
        assert result_image.mode == "RGB"

    def test_error_avatar_optimization(self):
        with pytest.raises(ImageExtensionError):
            avatar_optimization(b"not an image at all")

    @pytest.mark.parametrize(
        "w, h, mode, image_format, expected_w, expected_h",
        [
            (1200, 1080, "RGB", "JPEG", 1200, 1080),
            (600, 800, "RGB", "JPEG", 600, 800),
            (100, 100, "RGBA", "PNG", 100, 100),
            (1920, 1080, "P", "PNG", 1200, 675),
            (2400, 1200, "L", "PNG", 1200, 600),
        ],
    )
    def test_offer_optimization(
        self,
        w: int,
        h: int,
        mode: str,
        image_format: str,
        expected_w: int,
        expected_h: int,
    ):
        raw_bytes = self.generate_image_bytes((w, h), mode, image_format)
        offer_bytes = offer_optimization(raw_bytes)

        result_image = Image.open(io.BytesIO(offer_bytes))

        assert result_image.size == (expected_w, expected_h)
        assert result_image.format == "JPEG"
        assert result_image.mode == "RGB"

    def test_error_offer_optimization(self):
        with pytest.raises(ImageExtensionError):
            offer_optimization(b"not_an_image")
