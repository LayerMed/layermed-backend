from fastapi import status

from src.core.exceptions import AppError


class CityAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "City with this name already exists"


class CityNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "City not found"
