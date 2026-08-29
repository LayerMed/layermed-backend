from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.reviews.schemas import ReviewCreate, ReviewFilterParams, ReviewRead
from src.modules.reviews.service import create_review, get_reviews_by_filter
from src.modules.users.schemas import UserRead
from src.core.database import get_session
from src.core.dependencies import get_admin_user, get_current_user
from src.core.redis import RedisCache, get_redis

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
@router.get("/", response_model=list[ReviewRead], summary="Get doctor reviews")
async def get_reviews_by_filter_handle(
    doctor_id: int,
    filters: ReviewFilterParams,
    db: AsyncSession = Depends(get_session),
):
    return await get_reviews_by_filter(doctor_id, filters, db)
