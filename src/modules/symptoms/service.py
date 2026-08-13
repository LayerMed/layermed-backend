from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.symptoms.models import Symptom
from src.modules.symptoms.schemas import SymptomCreate, SymptomUpdate


async def get_symptoms(
    db: AsyncSession,
):
    query = select(Symptom)
    result = await db.execute(query)
    symptoms = result.scalars().all()
    return symptoms


async def get_symptom_by_id(symptom_id: int, db: AsyncSession):
    query = select(Symptom).filter(Symptom.id == symptom_id)
    result = await db.execute(query)
    symptom = result.scalar_one_or_none()
    return symptom


async def create_symptom(new_symptom: SymptomCreate, db: AsyncSession):
    try:
        query = (
            insert(Symptom)
            .values(name=new_symptom.name, description=new_symptom.description)
            .returning(Symptom)
        )
        result = await db.execute(query)
        created_symptom = result.scalar_one_or_none()
        return created_symptom
    except IntegrityError:
        return None


async def delete_symptom(symptom_id: int, db: AsyncSession):
    query = delete(Symptom).where(Symptom.id == symptom_id).returning(Symptom)
    result = await db.execute(query)
    deleted_symptom = result.scalar_one_or_none()
    return deleted_symptom


async def update_symptom(
    symptom_id: int, symptom_data: SymptomUpdate, db: AsyncSession
):
    update_data = symptom_data.model_dump(exclude_unset=True)

    if not update_data:
        return await get_symptom_by_id(symptom_id, db)

    query = (
        update(Symptom)
        .where(Symptom.id == symptom_id)
        .values(**update_data)
        .returning(Symptom)
    )

    result = await db.execute(query)
    updated_symptom = result.scalar_one_or_none()
    return updated_symptom
