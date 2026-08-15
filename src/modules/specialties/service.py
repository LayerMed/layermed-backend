from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.specialties.models import Specialty
from src.modules.specialties.schemas import SpecialtyCreate, SpecialtyUpdate


async def get_specialties(
    db: AsyncSession,
):
    query = select(Specialty)
    result = await db.execute(query)
    specialties = result.scalars().all()
    return specialties


async def get_specialty_by_id(specialty_id: int, db: AsyncSession):
    query = select(Specialty).filter(Specialty.id == specialty_id)
    result = await db.execute(query)
    specialty = result.scalar_one_or_none()
    return specialty


async def create_specialty(new_specialty: SpecialtyCreate, db: AsyncSession):
    try:
        query = (
            insert(Specialty)
            .values(name=new_specialty.name, description=new_specialty.description)
            .returning(Specialty)
        )
        result = await db.execute(query)
        created_specialty = result.scalar_one_or_none()
        return created_specialty
        await db.commit()
    except IntegrityError:
        return None


async def delete_specialty(specialty_id: int, db: AsyncSession):
    query = delete(Specialty).where(Specialty.id == specialty_id).returning(Specialty)
    result = await db.execute(query)
    deleted_speciality = result.scalar_one_or_none()
    await db.commit()
    return deleted_speciality


async def update_specialty(
    specialty_id: int, specialty_data: SpecialtyUpdate, db: AsyncSession
):
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
    return updated_specialty
