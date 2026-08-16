from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.cities.models import City
from src.modules.cities.schemas import CityCreate, CityUpdate


# CREATE
async def create_city(new_city: CityCreate, db: AsyncSession) -> City | None:
    try:
        query = insert(City).values(name=new_city.name).returning(City)
        result = await db.execute(query)
        created_city = result.scalar_one_or_none()
        await db.commit()
        return created_city
    except IntegrityError:
        return None


# READ
async def get_cities(db: AsyncSession) -> list[City]:
    query = select(City)
    result = await db.execute(query)
    cities = list(result.scalars().all())
    return cities


async def get_city_by_id(city_id: int, db: AsyncSession) -> City:
    query = select(City).filter(City.id == city_id)
    result = await db.execute(query)
    city = result.scalar_one_or_none()
    return city


# UPDATE
async def update_city(city_id: int, city_data: CityUpdate, db: AsyncSession) -> City | None:
    update_data = city_data.model_dump(exclude_unset=True)

    if not update_data:
        return await get_city_by_id(city_id, db)

    query = update(City).where(City.id == city_id).values(**update_data).returning(City)

    result = await db.execute(query)
    updated_city = result.scalar_one_or_none()
    await db.commit()
    return updated_city


# DELETE
async def delete_city(city_id: int, db: AsyncSession) -> City | None:
    query = delete(City).where(City.id == city_id).returning(City)
    result = await db.execute(query)
    deleted_city = result.scalar_one_or_none()
    await db.commit()
    return deleted_city