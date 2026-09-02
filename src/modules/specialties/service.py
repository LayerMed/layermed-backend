from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import CacheTTL
from src.core.redis import RedisCache
from src.modules.doctors.models import Doctor
from src.modules.specialties.exceptions import (
    SpecialtyAlreadyExistsError,
    SpecialtyNotFoundError,
)
from src.modules.specialties.models import Specialty
from src.modules.specialties.schemas import (
    SpecialtyCountRead,
    SpecialtyCreate,
    SpecialtyFilterParams,
    SpecialtyRead,
    SpecialtyUpdate,
)


# CREATE
async def create_specialty(
    new_specialty: SpecialtyCreate,
    db: AsyncSession,
    redis: RedisCache,
) -> SpecialtyRead:
    query = (
        insert(Specialty)
        .on_conflict_do_nothing()
        .values(name=new_specialty.name, description=new_specialty.description)
        .returning(Specialty)
    )
    result = await db.execute(query)
    created_specialty = result.scalar_one_or_none()
    if created_specialty is None:
        raise SpecialtyAlreadyExistsError()
    await db.commit()
    await redis.invalidate("specialties")
    return SpecialtyRead.model_validate(created_specialty)


# READ
async def get_specialties(
    filters: SpecialtyFilterParams,
    db: AsyncSession,
    redis: RedisCache,
) -> list[SpecialtyRead]:
    if filters.ids:
        query = select(Specialty).where(Specialty.id.in_(filters.ids))
        result = await db.execute(query)
        return [SpecialtyRead.model_validate(s) for s in result.scalars().all()]

    is_default = filters.is_default_page()
    cache_key = redis.build_key("specialties", "list", "default")

    if is_default:
        cached = await redis.getc(cache_key)
        if cached:
            return [SpecialtyRead.model_validate(s) for s in cached]

    query = select(Specialty).limit(filters.limit).offset(filters.offset)
    result = await db.execute(query)
    specialties = result.scalars().all()
    specialties_dto = [SpecialtyRead.model_validate(s) for s in specialties]

    if is_default:
        await redis.setc(cache_key, specialties_dto, ex=CacheTTL.STATIC)

    return specialties_dto


async def get_specialties_count(
    db: AsyncSession, redis: RedisCache
) -> list[SpecialtyCountRead]:
    cache_key = redis.build_key("specialties", "items", "count")
    cached_count = await redis.getc(cache_key)
    if cached_count:
        return [SpecialtyCountRead.model_validate(s) for s in cached_count]

    query = (
        select(
            Specialty.id, Specialty.name, func.count(Doctor.id).label("doctors_count")
        )
        .outerjoin(Specialty.doctors)
        .group_by(Specialty.id, Specialty.name)
        .order_by(Specialty.name)
    )
    result = await db.execute(query)
    specialties = result.all()
    specialties_dto = [SpecialtyCountRead.model_validate(s) for s in specialties]

    await redis.setc(cache_key, specialties_dto, CacheTTL.STATIC)
    return specialties_dto


async def get_specialty_by_id(
    specialty_id: int, db: AsyncSession, redis: RedisCache
) -> SpecialtyRead:
    cache_key = redis.build_key("specialties", "items", specialty_id)
    cached_specialty = await redis.getc(cache_key)
    if cached_specialty:
        return SpecialtyRead.model_validate(cached_specialty)

    query = select(Specialty).filter(Specialty.id == specialty_id)
    result = await db.execute(query)
    specialty = result.scalar_one_or_none()

    if specialty is None:
        raise SpecialtyNotFoundError()

    specialty_dto = SpecialtyRead.model_validate(specialty)
    await redis.setc(cache_key, specialty_dto, ex=CacheTTL.STATIC)

    return specialty_dto


# UPDATE
async def update_specialty(
    specialty_id: int,
    specialty_data: SpecialtyUpdate,
    db: AsyncSession,
    redis: RedisCache,
) -> SpecialtyRead:
    update_data = specialty_data.model_dump(exclude_unset=True)

    if not update_data:
        return await get_specialty_by_id(specialty_id, db, redis)

    query = (
        update(Specialty)
        .where(Specialty.id == specialty_id)
        .values(**update_data)
        .returning(Specialty)
    )

    result = await db.execute(query)
    updated_specialty = result.scalar_one_or_none()
    if updated_specialty is None:
        raise SpecialtyNotFoundError()
    await db.commit()
    await redis.invalidate("specialties")
    return SpecialtyRead.model_validate(updated_specialty)


# DELETE
async def delete_specialty(
    specialty_id: int, db: AsyncSession, redis: RedisCache
) -> None:
    query = delete(Specialty).where(Specialty.id == specialty_id).returning(Specialty)
    result = await db.execute(query)
    deleted_speciality = result.scalar_one_or_none()
    if deleted_speciality is None:
        raise SpecialtyNotFoundError()
    await db.commit()
    await redis.invalidate("specialties")
