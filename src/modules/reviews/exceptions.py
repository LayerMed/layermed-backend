from src.core.exceptions import AppError
from fastapi import status


class ReviewAlreadyLeft(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "You have already left feedback to this doctor"
