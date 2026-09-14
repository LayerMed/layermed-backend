from fastapi import status

from src.common.exceptions import AppError


class ImageWeightError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    detail = "The image weight is too large"


class ImageExtensionError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    detail = "Don't supported data type"


class MegabyteNotLessNull(AppError):
    detail = "The megabyte value must not be less than 0"

class ImageDimensionsError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Image resolution is too large or corrupted"