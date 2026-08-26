from fastapi import status
from src.core.exceptions import AppError


class UserAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "User with this email already exists"


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Incorrect email or password"


class UserNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "User not found"


class IncorrectPasswordError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Incorrect password"
