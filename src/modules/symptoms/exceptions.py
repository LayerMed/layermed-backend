from fastapi import status
from src.core.exceptions import AppError


class SymptomAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Symptom with such name already exists"


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Error with update"


class SymptomNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Symptom not found"
