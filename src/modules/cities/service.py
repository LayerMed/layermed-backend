import sqlalchemy.exc
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import CacheTTL
from src.core.redis import RedisCache
from src.modules.cities.exceptions import CityAlreadyExistsError, CityNotFoundError
from src.modules.cities.models import City
from src.modules.cities.schemas import CityCreate, CityRead, CityUpdate


# CREATE
async def create_city(
    new_city: CityCreate, db: AsyncSession, redis: RedisCache
) -> CityRead:
    query = (
        insert(City).on_conflict_do_nothing().values(name=new_city.name).returning(City)
    )
    result = await db.execute(query)
    created_city = result.scalar_one_or_none()

    if created_city is None:
        raise CityAlreadyExistsError()

    await db.commit()
    await redis.invalidate("cities")
    return CityRead.model_validate(created_city)


# READ
async def get_cities(db: AsyncSession, redis: RedisCache) -> list[CityRead]:
    cache_key = redis.build_key("cities", "items", "all")
    cached_cities = await redis.getc(cache_key)
    if cached_cities:
        return [CityRead.model_validate(c) for c in cached_cities]

    query = select(City)
    result = await db.execute(query)
    cities = result.scalars().all()

    cities_dto = [CityRead.model_validate(c) for c in cities]
    await redis.setc(cache_key, cities_dto, CacheTTL.STATIC)
    return cities_dto


async def get_city_by_id(city_id: int, db: AsyncSession, redis: RedisCache) -> CityRead:
    cache_key = redis.build_key("cities", "items", city_id)
    cached_city = await redis.getc(cache_key)
    if cached_city is not None:
        return CityRead.model_validate(cached_city)

    query = select(City).filter(City.id == city_id)
    result = await db.execute(query)
    city = result.scalar_one_or_none()
    if city is None:
        raise CityNotFoundError()

    city_dto = CityRead.model_validate(city)
    await redis.setc(cache_key, city_dto, CacheTTL.STATIC)

    return city_dto


# UPDATE
async def update_city(
    city_id: int, city_data: CityUpdate, db: AsyncSession, redis: RedisCache
) -> CityRead:
    update_data = city_data.model_dump(exclude_unset=True)

    if not update_data:
        return await get_city_by_id(city_id, db, redis)

    try:
        query = (
            update(City).where(City.id == city_id).values(**update_data).returning(City)
        )
        result = await db.execute(query)
        updated_city = result.scalar_one_or_none()
        if updated_city is None:
            raise CityNotFoundError()

        await db.commit()
        await redis.invalidate("cities")
        return CityRead.model_validate(updated_city)
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise CityAlreadyExistsError()


# DELETE
async def delete_city(city_id: int, db: AsyncSession, redis: RedisCache) -> None:
    query = delete(City).where(City.id == city_id).returning(City)
    result = await db.execute(query)
    deleted_city = result.scalar_one_or_none()
    if deleted_city is None:
        raise CityNotFoundError()

    await db.commit()
    await redis.invalidate("cities")
