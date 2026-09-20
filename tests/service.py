import io

from PIL import Image


def create_test_image(
    format: str = "JPEG", size: tuple[int, int] = (100, 100)
) -> io.BytesIO:
    file = io.BytesIO()
    image = Image.new("RGB", size, color="blue")
    image.save(file, format=format)
    file.seek(0)
    return file
