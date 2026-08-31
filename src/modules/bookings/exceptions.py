from fastapi import status

from src.core.exceptions import AppError


class OfferNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Offer is not found or it is inactive"


class BookingNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Booking not found"


class BookingAccessDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Access denied"


class BookingCannotBeCancelledError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, current_status: str):
        self.detail = f"Cannot cancel booking with status: {current_status}"
        super().__init__(self.detail)
