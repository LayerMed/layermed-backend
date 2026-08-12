

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_cache.decorator import cache
from src.modules.symptoms.service import get_symptom_by_id, get_symptoms
from src.core.database import get_session
from src.core.logs import logger


router = APIRouter(prefix="/symptoms", tags=["Symptoms"])


@router.get(
    "/", 
    summary="Get all symptoms",
    description="Get all symptoms from database"
)
@cache(expire=600)
async def get_symptoms_handle(
    db: AsyncSession = Depends(get_session),     
):
    symptoms = await get_symptoms(db)
    return symptoms


@router.get(
    "/symptom/{id}", 
    summary="Get symptom by id",
    description="Get one symptom from database via id",
)
@cache(expire=100)
async def get_symptom_by_id_handle(
    symptom_id: int, 
    db: AsyncSession = Depends(get_session)    
):
    symptom = get_symptom_by_id(symptom_id, db)
    if symptom is None:
        logger.warning(
            "Failed to fetch symptom: Symptom with id {id} not found or is a doctor",
            id=symptom_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return symptom


