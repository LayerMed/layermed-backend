from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.symptoms.models import Symptom
from src.modules.symptoms.schemas import SymptomCreate, SymptomUpdate


# CREATE
async def create_symptom(
    new_symptom: SymptomCreate,
    db: AsyncSession
) -> Symptom | None:
    try:
        query = (
            insert(Symptom)
            .values(name=new_symptom.name, description=new_symptom.description)
            .returning(Symptom)
        )
        result = await db.execute(query)
        created_symptom = result.scalar_one_or_none()
        await db.commit()
        return created_symptom
    except IntegrityError:
        return None


# READ
async def get_symptoms(
    db: AsyncSession,
) -> list[Symptom]:
    query = select(Symptom)
    result = await db.execute(query)
    symptoms = list(result.scalars().all())
    return symptoms


async def get_symptom_by_id(
    symptom_id: int, 
    db: AsyncSession
) -> Symptom | None:
    query = select(Symptom).filter(Symptom.id == symptom_id)
    result = await db.execute(query)
    symptom = result.scalar_one_or_none()
    return symptom


# UPDATE
async def update_symptom(
    symptom_id: int,
    symptom_data: SymptomUpdate,
    db: AsyncSession,
) -> Symptom | None:
    updated_symptom = await db.get(Symptom, symptom_id)
    if updated_symptom is None:
        return None
    update_data = symptom_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(updated_symptom, field, value)
    await db.commit()
    return updated_symptom


# DELETE
async def delete_symptom(
    symptom_id: int, 
    db: AsyncSession
) -> Symptom | None:
    query = delete(Symptom).where(Symptom.id == symptom_id).returning(Symptom)
    result = await db.execute(query)
    deleted_symptom = result.scalar_one_or_none()
    await db.commit()
    return deleted_symptom

