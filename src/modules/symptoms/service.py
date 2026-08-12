

from sqlalchemy import select

from src.modules.symptoms.models import Symptom
from sqlalchemy.ext.asyncio import AsyncSession


async def get_symptoms(
    db: AsyncSession,     
):
    query = select(Symptom)
    result = await db.execute(query)
    symptoms = result.scalars().all()
    return symptoms


async def get_symptom_by_id(
    symptom_id: int,
    db: AsyncSession     
):
    query = select(Symptom).filter(Symptom.id == symptom_id)
    result = await db.execute(query)
    symptoms = result.scalar_one_or_none()
    return symptoms