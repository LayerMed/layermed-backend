from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user
from src.core.redis import RedisCache, get_redis
from src.modules.cities.schemas import CityCreate, CityRead, CityUpdate
from src.modules.cities.service import (
    create_city,
    delete_city,
    get_cities,
    get_city_by_id,
    update_city,
)
from src.modules.users.models import User

router = APIRouter(prefix="/cities", tags=["Cities"])


# CREATE
@router.post(
    "/",
    response_model=CityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create city",
)
async def create_city_handle(
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
async def get_cities_handle(
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> list[CityRead]:
    return await get_cities(db, redis)


@router.get(
    "/{city_id}",
    response_model=CityRead,
    summary="Get city by id",
)
async def get_city_by_id_handle(
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
async def update_city_by_id_handle(
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
async def delete_city_handle(
    city_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> None:
    await delete_city(city_id, db, redis)
