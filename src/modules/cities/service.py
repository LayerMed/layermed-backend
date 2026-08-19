
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.redis import RedisCache
from src.modules.cities.models import City
from src.modules.cities.schemas import CityCreate, CityRead, CityUpdate


# CREATE
async def create_city(
    new_city: CityCreate, db: AsyncSession, redis: RedisCache
) -> CityRead | None:
    try:
        query = insert(City).values(name=new_city.name).returning(City)
        result = await db.execute(query)
        created_city = result.scalar_one_or_none()
        await db.commit()
        await redis.invalidate("cities")
        return CityRead.model_validate(created_city)
    except IntegrityError:
        await db.rollback()
        return None


# READ
async def get_cities(db: AsyncSession, redis: RedisCache) -> list[CityRead]:
    query = select(City)
    result = await db.execute(query)
    cities = result.scalars().all()
    if cities is None:
        return cities
    cities_dto = [CityRead.model_validate(c) for c in cities]
    await redis.setc(
        redis.build_key("cities", "items", "all"),
        [c.model_dump(mode="json") for c in cities_dto],
        ex=7200,
    )
    return cities_dto


async def get_city_by_id(
    city_id: int, db: AsyncSession, redis: RedisCache
) -> CityRead | None:
    cache_key = redis.build_key("cities", "items", city_id)
    cached_city = await redis.getc(cache_key)
    if cache_key:
        return CityRead.model_validate(cached_city)

    query = select(City).filter(City.id == city_id)
    result = await db.execute(query)
    city = result.scalar_one_or_none()

    city_dto = CityRead.model_validate(city)
    await redis.setc(cache_key, city_dto, 3600)

    return city_dto


# UPDATE
async def update_city(
    city_id: int, city_data: CityUpdate, db: AsyncSession, redis: RedisCache
) -> CityRead | None:
    update_data = city_data.model_dump(exclude_unset=True)

    if not update_data:
        return await get_city_by_id(city_id, db, redis)

    query = update(City).where(City.id == city_id).values(**update_data).returning(City)

    result = await db.execute(query)
    updated_city = result.scalar_one_or_none()
    await db.commit()
    await redis.invalidate("cities")
    return CityRead.model_validate(updated_city)


# DELETE
async def delete_city(city_id: int, db: AsyncSession, redis: RedisCache) -> bool:
    query = delete(City).where(City.id == city_id).returning(City)
    result = await db.execute(query)
    deleted_city = result.scalar_one_or_none()
    if deleted_city is None:
        return False
    await db.commit()
    await redis.invalidate("cities")
    return True
