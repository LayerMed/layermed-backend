from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.enums import RateLimit
from src.core.limiter import limiter
from src.core.dependencies import get_admin_user
from src.modules.cities.schemas import CityCreate, CityRead, CityUpdate
from src.modules.cities.service import (
    create_city,
    delete_city,
    get_cities,
    get_city_by_id,
    update_city,
)
from src.modules.users.models import User
from src.services.storage.postgres import get_session
from src.services.storage.redis import RedisCache, get_redis

router = APIRouter(prefix="/cities", tags=["Cities"])


# CREATE
@router.post(
    "/",
    response_model=CityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create city",
)
@limiter.limit(RateLimit.MUTATION)
async def create_city_handle(
    request: Request,
    new_city: CityCreate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> CityRead:
    return await create_city(new_city, db, redis)


# READ
@router.get(
    "/",
    response_model=list[CityRead],
    summary="Get all cities",
)
@limiter.limit(RateLimit.BURST)
async def get_cities_handle(
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> list[CityRead]:
    return await get_cities(db, redis)


@router.get(
    "/{city_id}",
    response_model=CityRead,
    summary="Get city by id",
)
@limiter.limit(RateLimit.READ)
async def get_city_by_id_handle(
    request: Request,
    city_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> CityRead:
    return await get_city_by_id(city_id, db, redis)


# UPDATE
@router.patch(
    "/{city_id}",
    response_model=CityRead,
    summary="Update city",
)
@limiter.limit(RateLimit.MUTATION)
async def update_city_by_id_handle(
    request: Request,
    city_id: int,
    city_data: CityUpdate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> CityRead:
    return await update_city(city_id, city_data, db, redis)


# DELETE
@router.delete(
    "/{city_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete city",
)
@limiter.limit(RateLimit.MUTATION)
async def delete_city_handle(
    request: Request,
    city_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> None:
    await delete_city(city_id, db, redis)
