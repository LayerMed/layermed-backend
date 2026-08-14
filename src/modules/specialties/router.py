from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user
from src.core.logs import logger
from src.modules.specialties.schemas import (
    SpecialtyCreate,
    SpecialtyRead,
    SpecialtyUpdate,
)
from src.modules.specialties.service import (
    create_specialty,
    delete_specialty,
    get_specialties,
    get_specialty_by_id,
    update_specialty,
)
from src.modules.users.models import User


router = APIRouter(prefix="/specialties", tags=["specialties"])


# Admin
@router.post(
    "/",
    response_model=SpecialtyRead,
    summary="Create specialty",
    status_code=status.HTTP_201_CREATED,
    description="Create specialty in database",
)
async def create_specialty_handle(
    new_specialty: SpecialtyCreate,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    created_specialty = await create_specialty(new_specialty, db)
    if created_specialty is None:
        logger.warning(
            "Specialty with this name: {name} already exists",
            name=new_specialty.name,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specialty with this name already exists",
        )
    return created_specialty


@router.delete(
    "/{specialty_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete specialty",
    description="Delete specialty from database",
)
async def delete_specialty_handle(
    specialty_id: int,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    deleted_specialty = await delete_specialty(specialty_id, db)
    if deleted_specialty is None:
        logger.info(
            "A specialty with this id does not exist: {specialty_id}",
            specialty_id=specialty_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A specialty with this id does not exist: {specialty_id}",
        )

    return deleted_specialty


@router.patch(
    "/{specialty_id}",
    response_model=SpecialtyRead,
    summary="Update specialty",
    description="Update specialty in database",
)
async def update_specialty_by_id_handle(
    specialty_id: int,
    specialty_data: SpecialtyUpdate,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    updated_specialty = await update_specialty(specialty_id, specialty_data, db)
    if updated_specialty is None:
        logger.warning(
            "Failed to fetch specialty: Specialty with id {specialty_id} not found",
            specialty_id=specialty_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Specialty not found"
        )
    return updated_specialty


# GET
@router.get(
    "/",
    response_model=list[SpecialtyRead],
    summary="Get all specialties",
    description="Get all specialties from database",
)
async def get_specialties_handle(
    db: AsyncSession = Depends(get_session),
):
    specialties = await get_specialties(db)
    return specialties


@router.get(
    "/{specialty_id}",
    response_model=SpecialtyRead,
    summary="Get specialty by id",
    description="Get one specialty from database via id",
)
async def get_specialty_by_id_handle(
    specialty_id: int, db: AsyncSession = Depends(get_session)
):
    specialty = await get_specialty_by_id(specialty_id, db)
    if specialty is None:
        logger.warning(
            "Failed to fetch specialty: Specialty with id {specialty_id} not found",
            specialty_id=specialty_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Specialty not found"
        )

    return specialty
