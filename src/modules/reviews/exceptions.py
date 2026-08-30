from src.core.exceptions import AppError
from fastapi import status


class ReviewAlreadyLeft(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "You have already left feedback to this doctor"


class ReviewNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Review not found"


class ReviewAccessDeletionError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You can only delete your own reviews"