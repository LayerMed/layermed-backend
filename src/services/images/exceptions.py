from fastapi import status

from src.common.exceptions import AppError


class ImageWeightError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    detail = "The image weight is too large"


class ImageExtensionError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    detail = "Don't supported data type"
