from src.core.exceptions import AppError
from fastapi import status


class ItemNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Item not found"
