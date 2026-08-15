from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user
from src.core.logs import logger
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


# ADMIN
@router.post(
    "/",
    response_model=SymptomRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create symptom",
)
async def create_symptom_handle(
    new_symptom: SymptomCreate,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    created_symptom = await create_symptom(new_symptom, db)
    if created_symptom is None:
        logger.warning(
            "Symptom with this name: {name} already exists", name=new_symptom.name
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
):
    symptoms = await get_symptoms(db)
    return symptoms


@router.get(
    "/{symptom_id}",
    response_model=SymptomRead,
    summary="Get symptom by id",
)
async def get_symptom_by_id_handle(
    symptom_id: int, db: AsyncSession = Depends(get_session)
):
    symptom = await get_symptom_by_id(symptom_id, db)
    if symptom is None:
        logger.warning(
            "Failed to fetch symptom: Symptom with id {symptom_id} not found",
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
    admin: User = Depends(get_admin_user),
):
    updated_symptom = await update_symptom(symptom_id, symptom_data, db)
    if updated_symptom is None:
        logger.warning(
            "Failed to fetch symptom: Symptom with id {symptom_id} not found",
            symptom_id=symptom_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Symptom not found"
        )

    return updated_symptom


# DELETE
@router.delete(
    "/{symptom_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete symptom",
)
async def delete_symptom_handle(
    symptom_id: int,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    deleted_symptom = await delete_symptom(symptom_id, db)
    if deleted_symptom is None:
        logger.info(
            "A symptom with this id does not exist: {symptom_id}", symptom_id=symptom_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A symptom with this id does not exist: {symptom_id}",
        )

    return deleted_symptom
