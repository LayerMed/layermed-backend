from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import ReviewStatus
from src.core.redis import RedisCache
from src.core.schemas import PaginatedResponse
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRead
from src.modules.reviews.exceptions import (
    ReviewAccessDeletionError,
    ReviewAlreadyLeft,
    ReviewNotFoundError,
)
from src.modules.reviews.models import Review
from src.modules.reviews.schemas import (
    ReviewCreate,
    ReviewFilterParams,
    ReviewRead,
)
from src.modules.users.schemas import UserRead


async def recalculate_doctor_rating(
    doctor_id: int, rating_change: int, is_addition: bool, db: AsyncSession
) -> None:
    query_doctor = select(Doctor).where(Doctor.id == doctor_id)
    doctor_result = await db.execute(query_doctor)
    doctor = doctor_result.scalar_one()

    if is_addition:
        new_rating_avg = (doctor.rating_avg * doctor.reviews_count + rating_change) / (
            doctor.reviews_count + 1
        )
        new_reviews_count = doctor.reviews_count + 1
    else:
        if doctor.reviews_count > 1:
            new_rating_avg = (
                (doctor.rating_avg * doctor.reviews_count) - rating_change
            ) / (doctor.reviews_count - 1)
            new_reviews_count = doctor.reviews_count - 1
        else:
            new_rating_avg = 0.0
            new_reviews_count = 0

    query_update = (
        update(Doctor)
        .where(Doctor.id == doctor_id)
        .values(rating_avg=new_rating_avg, reviews_count=new_reviews_count)
    )
    await db.execute(query_update)


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
                status=ReviewStatus.APPROVED,
            )
            .returning(Review)
        )
        result = await db.execute(query)
        created_review = result.scalar_one()

        await recalculate_doctor_rating(
            doctor_id=new_review.doctor_id,
            rating_change=new_review.rating,
            is_addition=True,
            db=db,
        )

        await db.commit()
        await redis.delc(redis.build_key("doctors", "items", new_review.doctor_id))

        return ReviewRead.model_validate(created_review)

    except IntegrityError:
        await db.rollback()
        raise ReviewAlreadyLeft()


# READ
async def get_reviews_by_filter(
    doctor_id: int, filters: ReviewFilterParams, db: AsyncSession
) -> PaginatedResponse:

    query = select(Review).where(Review.doctor_id == doctor_id)

    if filters.rating is not None:
        query = query.where(Review.rating == filters.rating)
    if filters.is_positive is not None:
        if filters.is_positive:
            query = query.where(Review.rating >= 4)
        else:
            query = query.where(Review.rating <= 3)
    if filters.status is not None:
        query = query.where(Review.status == filters.status)

    query = (
        query.order_by(Review.created_at.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    )

    result = await db.execute(query)
    reviews = result.scalars().all()

    return PaginatedResponse[ReviewRead](
        items=[ReviewRead.model_validate(r) for r in reviews],
        limit=filters.limit,
        offset=filters.offset,
    )


# UPDATE
async def update_review_status(
    review_id: int,
    status: ReviewStatus,
    db: AsyncSession,
    redis: RedisCache,
) -> ReviewRead:
    review_query = select(Review).where(Review.id == review_id)
    review_result = await db.execute(review_query)
    review = review_result.scalar_one_or_none()

    if review is None:
        raise ReviewNotFoundError()

    old_status = review.status
    review.status = status

    if status == ReviewStatus.REJECTED and old_status != ReviewStatus.REJECTED:
        await recalculate_doctor_rating(
            doctor_id=review.doctor_id,
            rating_change=review.rating,
            is_addition=False,
            db=db,
        )
    elif status == ReviewStatus.APPROVED and old_status == ReviewStatus.REJECTED:
        await recalculate_doctor_rating(
            doctor_id=review.doctor_id,
            rating_change=review.rating,
            is_addition=True,
            db=db,
        )

    await db.commit()
    await redis.delc(redis.build_key("doctors", "items", review.doctor_id))
    return ReviewRead.model_validate(review)


async def remove_review_request(
    review_id: int, current_doctor: DoctorRead, db: AsyncSession, redis: RedisCache
) -> ReviewRead:
    query = select(Review).where(Review.id == review_id)
    result = await db.execute(query)
    review = result.scalar_one_or_none()

    if review is None:
        raise ReviewNotFoundError()

    if review.doctor_id != current_doctor.id:
        raise ReviewAccessDeletionError()

    return await update_review_status(review_id, ReviewStatus.PENDING, db, redis)


async def remove_review_by_user(
    review_id: int, current_user: UserRead, db: AsyncSession, redis: RedisCache
) -> None:
    query_review = select(Review).where(Review.id == review_id)
    result = await db.execute(query_review)
    review = result.scalar_one_or_none()
    if review is None:
        raise ReviewNotFoundError()

    if review.user_id != current_user.id:
        raise ReviewAccessDeletionError()

    query_delete = delete(Review).where(Review.id == review_id)
    await db.execute(query_delete)

    await recalculate_doctor_rating(
        doctor_id=review.doctor_id,
        rating_change=review.rating,
        is_addition=False,
        db=db,
    )

    await db.commit()
    await redis.delc(redis.build_key("doctors", "items", review.doctor_id))
