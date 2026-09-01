from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_current_user
from src.core.redis import RedisCache, get_redis
from src.modules.bookings.schemas import BookingCreate, BookingRead
from src.modules.bookings.service import (
    cancel_booking,
    create_booking,
    get_booking_by_id,
    get_current_bookings,
)
from src.modules.users.schemas import UserRead

router = APIRouter(prefix="/bookings", tags=["Bookings"])


# CREATE
@router.post(
    "/create",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create booking",
)
async def create_booking_handle(
    new_booking: BookingCreate,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> BookingRead:
    return await create_booking(new_booking, current_user, db, redis)


# READ
@router.get(
    "/my",
    response_model=list[BookingRead],
    summary="Get bookings of current user",
)
async def get_current_bookings_handle(
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> list[BookingRead]:
    return await get_current_bookings(current_user, db, redis)


@router.get(
    "/{booking_id}",
    response_model=BookingRead,
    summary="Get booking by id",
)
async def get_booking_by_id_handle(
    booking_id: int,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> BookingRead:
    return await get_booking_by_id(booking_id, current_user, db, redis)


# UPDATE
@router.patch(
    "/{booking_id}",
    response_model=BookingRead,
    summary="Cancel booking by id",
)
async def cancel_booking_handle(
    booking_id: int,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> BookingRead:
    return await cancel_booking(booking_id, current_user, db, redis)
