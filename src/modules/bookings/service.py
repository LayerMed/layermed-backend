from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.core.enums import BookingStatus, CacheTTL, ModerationStatus, UserRole
from src.core.redis import RedisCache
from src.modules.bookings.exceptions import (
    BookingAccessDeniedError,
    BookingCannotBeCancelledError,
    BookingNotFoundError,
    OfferNotFoundError,
)
from src.modules.bookings.models import Booking
from src.modules.bookings.schemas import BookingCreate, BookingRead
from src.modules.offers.models import Offer
from src.modules.users.schemas import UserRead


# CREATE
async def create_booking(
    new_booking: BookingCreate,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> BookingRead:
    query_offer = select(Offer).where(
        Offer.id == new_booking.offer_id, Offer.status == ModerationStatus.APPROVED
    )
    result = await db.execute(query_offer)
    offer = result.scalar_one_or_none()
    if offer is None:
        raise OfferNotFoundError()

    query = (
        insert(Booking)
        .values(
            user_id=current_user.id,
            offer_id=new_booking.offer_id,
            appointment_time=new_booking.appointment_time,
            status=BookingStatus.PENDING,
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
    await redis.setc(cache_key, bookings_dto, CacheTTL.FAST)

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
            raise BookingAccessDeniedError()

        return booking_dto

    query = (
        select(Booking)
        .options(joinedload(Booking.offer))
        .where(Booking.id == booking_id)
    )

    result = await db.execute(query)
    booking = result.scalar_one_or_none()

    if not booking:
        raise BookingNotFoundError()

    booking_dto = BookingRead.model_validate(booking)

    if booking_dto.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise BookingAccessDeniedError()

    await redis.setc(cache_key, booking_dto.model_dump(mode="json"), CacheTTL.FAST)

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
        raise BookingCannotBeCancelledError(booking.status)

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
