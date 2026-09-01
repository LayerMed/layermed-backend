from fastapi import status

from src.core.exceptions import AppError


class OfferAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Offer profile already exists"


class OfferNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Offer not found"


class OfferAccessDenied(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You cannot delete another doctor's offer"
