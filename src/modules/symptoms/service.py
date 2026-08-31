from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import CacheTTL
from src.core.redis import RedisCache
from src.modules.symptoms.exceptions import (
    SymptomAlreadyExistsError,
    SymptomNotFoundError,
)
from src.modules.symptoms.models import Symptom
from src.modules.symptoms.schemas import SymptomCreate, SymptomRead, SymptomUpdate


# CREATE
async def create_symptom(
    new_symptom: SymptomCreate, db: AsyncSession, redis: RedisCache
) -> SymptomRead:
    query = (
        insert(Symptom)
        .on_conflict_do_nothing()
        .values(name=new_symptom.name, description=new_symptom.description)
        .returning(Symptom)
    )
    result = await db.execute(query)
    created_symptom = result.scalar_one_or_none()
    if created_symptom is None:
        raise SymptomAlreadyExistsError()
    await db.commit()
    await redis.invalidate("symptoms")
    return SymptomRead.model_validate(created_symptom)


# READ
async def get_symptoms(db: AsyncSession, redis: RedisCache) -> list[SymptomRead]:
    cache_key = redis.build_key("symptoms", "items", "all")
    cached_symptoms = await redis.getc(cache_key)
    if cached_symptoms:
        return [SymptomRead.model_validate(s) for s in cached_symptoms]

    query = select(Symptom)
    result = await db.execute(query)
    symptoms = result.scalars().all()

    symptoms_dto = [SymptomRead.model_validate(s) for s in symptoms]
    await redis.setc(cache_key, symptoms_dto, CacheTTL.STATIC)

    return symptoms_dto


async def get_symptom_by_id(
    symptom_id: int,
    db: AsyncSession,
    redis: RedisCache,
) -> SymptomRead:
    cache_key = redis.build_key("symptoms", "items", symptom_id)
    cached_symptom = await redis.getc(cache_key)
    if cached_symptom:
        return SymptomRead.model_validate(cached_symptom)

    query = select(Symptom).filter(Symptom.id == symptom_id)
    result = await db.execute(query)
    symptom = result.scalar_one_or_none()
    if symptom is None:
        raise SymptomNotFoundError()

    symptom_dto = SymptomRead.model_validate(symptom)
    await redis.setc(cache_key, symptom_dto, CacheTTL.STATIC)

    return symptom_dto


# UPDATE
async def update_symptom(
    symptom_id: int,
    symptom_data: SymptomUpdate,
    db: AsyncSession,
    redis: RedisCache,
) -> SymptomRead:
    update_data = symptom_data.model_dump(exclude_unset=True)
    query = (
        update(Symptom)
        .where(Symptom.id == symptom_id)
        .values(**update_data)
        .returning(Symptom)
    )

    result = await db.execute(query)
    updated_symptom = result.scalar_one_or_none()
    if updated_symptom is None:
        raise SymptomNotFoundError()
    await db.commit()

    await redis.invalidate("symptoms")    
    return SymptomRead.model_validate(updated_symptom)


# DELETE
async def delete_symptom(symptom_id: int, db: AsyncSession, redis: RedisCache) -> None:
    query = delete(Symptom).where(Symptom.id == symptom_id).returning(Symptom)
    result = await db.execute(query)
    deleted_symptom = result.scalar_one_or_none()

    if deleted_symptom is None:
        raise SymptomNotFoundError()
    await db.commit()
    await redis.invalidate("symptoms")
