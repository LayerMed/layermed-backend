from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.redis import RedisCache
from src.modules.specialties.models import Specialty
from src.modules.specialties.schemas import (
    SpecialtyCreate,
    SpecialtyRead,
    SpecialtyUpdate,
)


# CREATE
async def create_specialty(
    new_specialty: SpecialtyCreate, db: AsyncSession
) -> SpecialtyRead | None:
    try:
        query = (
            insert(Specialty)
            .values(name=new_specialty.name, description=new_specialty.description)
            .returning(Specialty)
        )
        result = await db.execute(query)
        created_specialty = result.scalar_one_or_none()
        await db.commit()
        return SpecialtyRead.model_validate(created_specialty)
    except IntegrityError:
        await db.rollback()
        return None


# READ
async def get_specialties(
    ids: list[int] | None,
    db: AsyncSession,
) -> list[Specialty]:
    if ids is None:
        query = select(Specialty)
    else:
        query = select(Specialty).where(Specialty.id.in_(ids))
    result = await db.execute(query)
    specialties = list(result.scalars().all())
    return specialties


async def get_specialty_by_id(
    specialty_id: int, db: AsyncSession
) -> SpecialtyRead | None:
    query = select(Specialty).filter(Specialty.id == specialty_id)
    result = await db.execute(query)
    specialty = result.scalar_one_or_none()
    return SpecialtyRead.model_validate(specialty)


# UPDATE
async def update_specialty(
    specialty_id: int, specialty_data: SpecialtyUpdate, db: AsyncSession
) -> SpecialtyRead | None:
    update_data = specialty_data.model_dump(exclude_unset=True)

    if not update_data:
        return await get_specialty_by_id(specialty_id, db)

    query = (
        update(Specialty)
        .where(Specialty.id == specialty_id)
        .values(**update_data)
        .returning(Specialty)
    )

    result = await db.execute(query)
    updated_specialty = result.scalar_one_or_none()
    await db.commit()
    return SpecialtyRead.model_validate(updated_specialty)


# DELETE
async def delete_specialty(specialty_id: int, db: AsyncSession) -> bool:
    query = delete(Specialty).where(Specialty.id == specialty_id).returning(Specialty)
    result = await db.execute(query)
    deleted_speciality = result.scalar_one_or_none()
    if deleted_speciality is None:
        return False
    await db.commit()
    return True
