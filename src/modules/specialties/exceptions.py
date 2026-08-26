from fastapi import status
from src.core.exceptions import AppError


class SpecialtyAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Symptom  with such name already exists"


class SpecialtyNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Symptom not found"
