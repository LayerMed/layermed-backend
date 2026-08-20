from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user
from src.core.logs import logger
from src.core.redis import RedisCache, get_redis
from src.modules.symptoms.schemas import SymptomCreate, SymptomRead, SymptomUpdate
from src.modules.symptoms.service import (
    create_symptom,
    delete_symptom,
    get_symptom_by_id,
    get_symptoms,
    update_symptom,
)
from src.modules.users.models import User

router = APIRouter(prefix="/symptoms", tags=["Symptoms"])


# CREATE
@router.post(
    "/",
    response_model=SymptomRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create symptom",
)
async def create_symptom_handle(
    new_symptom: SymptomCreate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> SymptomRead:  
    created_symptom = await create_symptom(new_symptom, db, redis)
    if created_symptom is None:
        logger.warning(
            "Symptom with this name: {name} already exists", name=new_symptom.name
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Symptom with this name already exists",
        )
    return created_symptom


# READ
@router.get(
    "/",
    response_model=list[SymptomRead],
    summary="Get all symptoms",
)
async def get_symptoms_handle(
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> list[SymptomRead]:
    symptoms = await get_symptoms(db, redis)
    return symptoms


@router.get(
    "/{symptom_id}",
    response_model=SymptomRead,
    summary="Get symptom by id",
)
async def get_symptom_by_id_handle(
    symptom_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> SymptomRead:
    symptom = await get_symptom_by_id(symptom_id, db, redis)
    if symptom is None:
        logger.warning(
            "Symptom with id {symptom_id} not found",
            symptom_id=symptom_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Symptom not found"
        )
    return symptom


# UPDATE
@router.patch(
    "/{symptom_id}",
    response_model=SymptomRead,
    summary="Update symptom",
)
async def update_symptom_by_id_handle(
    symptom_id: int,
    symptom_data: SymptomUpdate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> SymptomRead:
    updated_symptom = await update_symptom(symptom_id, symptom_data, db, redis)
    if updated_symptom is None:
        logger.warning(
            "Symptom with id {symptom_id} not found",
            symptom_id=symptom_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Symptom not found"
        )
    return updated_symptom


# DELETE
@router.delete(
    "/{symptom_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete symptom",
)
async def delete_symptom_handle(
    symptom_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> None:
    success = await delete_symptom(symptom_id, db, redis)
    if not success:
        logger.info(
            "A symptom with this id does not exist: {symptom_id}", symptom_id=symptom_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A symptom does not exist",
        )
