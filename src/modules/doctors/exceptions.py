from fastapi import status
from src.core.exceptions import AppError


class DoctorProfileAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Doctor profile already exists"


class DoctorNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Doctor not found"


class SpecialtiesNotFoundError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "One or more specialties not found"


class IncorrectPasswordError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Incorrect password"
