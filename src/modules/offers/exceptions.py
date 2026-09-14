from fastapi import status

from src.common.exceptions import AppError


class OfferAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Offer profile already exists"


class OfferNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Offer not found"


class OfferAccessDenied(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You do not have the rights to access this offer."


class OfferImagesError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Images don't uploaded"


class OfferImagesCountError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Images count exceeds the limit of 10 pieces"


class OfferImageNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Image not found in this offer"