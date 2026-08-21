from fastapi import HTTPException, status
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.core.enums import BookingStatus, UserRole
from src.core.redis import RedisCache
from src.modules.bookings.models import Booking
from src.modules.bookings.schemas import BookingCreate, BookingRead
from src.modules.suggestions.models import Suggestion
from src.modules.users.schemas import UserRead


# CREATE
async def create_booking(
    new_booking: BookingCreate,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> BookingRead:
    query_suggestion = select(Suggestion).where(
        Suggestion.id == new_booking.suggestion_id, Suggestion.is_active == True
    )
    result = await db.execute(query_suggestion)
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion is not found or it is inactive",
        )

    query = (
        insert(Booking)
        .values(
            user_id=current_user.id,
            suggestion_id=new_booking.suggestion_id,
            appointment_time=new_booking.appointment_time,
        )
        .returning(Booking)
    )
    result = await db.execute(query)
    booking = result.scalars().first()
    await db.commit()

    cache_key = redis.build_key("bookings", "user", current_user.id)
    await redis.delc(cache_key)

    return BookingRead.model_validate(booking)


# READ
async def get_current_bookings(
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> list[BookingRead]:
    cache_key = redis.build_key("bookings", "user", current_user.id)
    cached_bookings = await redis.getc(cache_key)
    if cached_bookings:
        return [BookingRead.model_validate(b) for b in cached_bookings]

    query = select(Booking).where(Booking.user_id == current_user.id)
    result = await db.execute(query)
    bookings = result.scalars().all()

    bookings_dto = [BookingRead.model_validate(b) for b in bookings]
    await redis.setc(cache_key, [s.model_dump(mode="json") for s in bookings_dto], 3600)

    return bookings_dto


async def get_booking_by_id(
    booking_id: int,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> BookingRead:
    cache_key = redis.build_key("bookings", "id", booking_id)
    cached_booking = await redis.getc(cache_key)
    if cached_booking:
        booking_dto = BookingRead.model_validate(cached_booking)
        if (
            booking_dto.user_id != current_user.id
            and current_user.role != UserRole.ADMIN
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

        return booking_dto    

    query = (
        select(Booking)
        .options(joinedload(Booking.suggestion))
        .where(Booking.id == booking_id)
    )

    result = await db.execute(query)
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )    

    booking_dto = BookingRead.model_validate(booking)
    await redis.setc(cache_key, booking_dto.model_dump(mode="json"), 3600)

    return booking_dto


# UPDATE
async def cancel_booking(
    booking_id: int,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> BookingRead:
    booking = await get_booking_by_id(booking_id, current_user, db, redis)

    if booking.status in (
        BookingStatus.CANCELLED,
        BookingStatus.COMPLETED,
        BookingStatus.NO_SHOW,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel booking with status: {booking.status}",
        )

    stmt = (
        update(Booking)
        .where(Booking.id == booking_id)
        .values(status=BookingStatus.CANCELLED)
        .returning(Booking)
    )
    result = await db.execute(stmt)
    updated_booking = result.scalars().first()
    await db.commit()

    cache_key_user = redis.build_key("bookings", "user", current_user.id)
    cache_key_id = redis.build_key("bookings", "id", booking_id)
    await redis.delc(cache_key_user)
    await redis.delc(cache_key_id)

    return BookingRead.model_validate(updated_booking)
