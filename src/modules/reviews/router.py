from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user, get_current_doctor, get_current_user
from src.core.enums import ModerationStatus
from src.core.redis import RedisCache, get_redis
from src.core.schemas import PaginatedResponse
from src.modules.doctors.schemas import DoctorRead
from src.modules.reviews.schemas import ReviewCreate, ReviewFilterParams, ReviewRead
from src.modules.reviews.service import (
    create_review,
    get_reviews_by_filter,
    remove_review_by_user,
    remove_review_request,
    update_review_status,
)
from src.modules.users.schemas import UserRead

router = APIRouter(prefix="/reviews", tags=["Reviews"])


# CREATE
@router.post(
    "/",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create review",
)
async def create_review_handle(
    new_review: ReviewCreate,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> ReviewRead:
    return await create_review(new_review, current_user, db, redis)


# READ
@router.get(
    "/{doctor_id}",
    response_model=PaginatedResponse[ReviewRead],
    summary="Get doctor reviews",
)
async def get_reviews_by_filter_handle(
    doctor_id: int,
    filters: Annotated[ReviewFilterParams, Depends()],
    db: AsyncSession = Depends(get_session),
):
    return await get_reviews_by_filter(doctor_id, filters, db)


# UPDATE
@router.patch(
    "/review/{review_id}/appeal", summary="Doctor requests to remove the review"
)
async def remove_review_request_handle(
    review_id: int,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> ReviewRead:
    return await remove_review_request(review_id, current_doctor, db, redis)


@router.patch(
    "/review/{review_id}/approve-deletion",
    summary="Admin approves review deletion (Hide review & recalculate rating)",
    response_model=ReviewRead,
)
async def admin_approve_deletion_handle(
    review_id: int,
    admin: UserRead = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> ReviewRead:
    return await update_review_status(review_id, ModerationStatus.REJECTED, db, redis)


@router.patch(
    "/review/{review_id}/reject-deletion",
    summary="Admin rejects review deletion (Keep review active)",
    response_model=ReviewRead,
)
async def admin_reject_deletion_handle(
    review_id: int,
    admin: UserRead = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> ReviewRead:
    return await update_review_status(review_id, ModerationStatus.APPROVED, db, redis)


@router.patch(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete review",
)
async def remove_review_by_user_handle(
    review_id: int,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> None:
    await remove_review_by_user(review_id, current_user, db, redis)
