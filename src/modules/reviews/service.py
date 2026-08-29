from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select, update, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.doctors.models import Doctor
from src.modules.reviews.exceptions import ReviewAlreadyLeft
from src.modules.reviews.models import Review
from src.modules.reviews.schemas import (
    ReviewCreate,
    ReviewFilterParams,
    ReviewPaginatedResponse,
    ReviewRead,
)
from src.modules.users.schemas import UserRead
from src.core.redis import RedisCache


# CREATE
async def create_review(
    new_review: ReviewCreate,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> ReviewRead:
    try:
        query = (
            insert(Review)
            .values(
                user_id=current_user.id,
                doctor_id=new_review.doctor_id,
                rating=new_review.rating,
                comment=new_review.comment,
            )
            .returning(Review)
        )
        result = await db.execute(query)
        created_review = result.scalar_one()

        query_update_doctor = (
            update(Doctor)
            .where(Doctor.id == new_review.doctor_id)
            .values(
                rating_avg=(
                    Doctor.rating_avg * Doctor.reviews_count + new_review.rating
                )
                / (Doctor.reviews_count + 1),
                reviews_count=Doctor.reviews_count + 1,
            )
        )
        await db.execute(query_update_doctor)
        await db.commit()
        await redis.delc(redis.build_key("doctors", "items", new_review.doctor_id))

        return ReviewRead.model_validate(created_review)

    except IntegrityError:
        await db.rollback()
        raise ReviewAlreadyLeft()


# READ
async def get_reviews_by_filter(
    doctor_id: int, filters: ReviewFilterParams, db: AsyncSession
) -> ReviewPaginatedResponse:

    query = select(Review).where(Review.doctor_id == doctor_id)

    if filters.rating is not None:
        query = query.where(Review.rating == filters.rating)

    if filters.is_positive is not None:
        if filters.is_positive:
            query = query.where(Review.rating >= 4)
        else:
            query = query.where(Review.rating <= 3)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()

    query = (
        query.order_by(Review.created_at.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    )

    result = await db.execute(query)
    reviews = result.scalars().all()

    return ReviewPaginatedResponse(
        items=[ReviewRead.model_validate(r) for r in reviews],
        total=total_count,
        limit=filters.limit,
        offset=filters.offset,
    )
