from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.enums import RateLimit
from src.core.dependencies import get_current_user
from src.core.limiter import limiter
from src.modules.bookings.schemas import BookingCreate, BookingRead
from src.modules.bookings.service import (
    cancel_booking,
    create_booking,
    get_booking_by_id,
    get_current_bookings,
)
from src.modules.users.schemas import UserRead
from src.services.storage.postgres import get_session
from src.services.storage.redis import RedisCache, get_redis

router = APIRouter(prefix="/bookings", tags=["Bookings"])


# CREATE
@router.post(
    "/create",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create booking",
)
@limiter.limit(RateLimit.MUTATION)
async def create_booking_handle(
    request: Request,
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
@limiter.limit(RateLimit.READ)
async def get_current_bookings_handle(
    request: Request,
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
@limiter.limit(RateLimit.READ)
async def get_booking_by_id_handle(
    request: Request,
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
@limiter.limit(RateLimit.MUTATION)
async def cancel_booking_handle(
    request: Request,
    booking_id: int,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> BookingRead:
    return await cancel_booking(booking_id, current_user, db, redis)
