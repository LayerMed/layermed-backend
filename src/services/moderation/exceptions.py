from fastapi import status

from src.common.exceptions import AppError


class ItemNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Item not found"
