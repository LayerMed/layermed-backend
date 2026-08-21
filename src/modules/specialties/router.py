from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user
from src.core.logs import logger
from src.core.redis import RedisCache, get_redis
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

router = APIRouter(prefix="/specialties", tags=["Specialties"])


# CREATE
@router.post(
    "/",
    response_model=SpecialtyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create specialty",
)
async def create_specialty_handle(
    new_specialty: SpecialtyCreate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> SpecialtyRead:
    created_specialty = await create_specialty(new_specialty, db, redis)
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


# READ
@router.get(
    "/",
    response_model=list[SpecialtyRead],
    summary="Get all specialties",
)
async def get_specialties_handle(
    ids: list[int] | None = Query(default=None),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> list[SpecialtyRead]:
    specialties = await get_specialties(ids, db, redis)
    return specialties


@router.get(
    "/{specialty_id}",
    response_model=SpecialtyRead,
    summary="Get specialty by id",
)
async def get_specialty_by_id_handle(
    specialty_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> SpecialtyRead:

    specialty = await get_specialty_by_id(specialty_id, db, redis)
    if specialty is None:
        logger.warning(
            "Specialty with id {specialty_id} not found",
            specialty_id=specialty_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Specialty not found"
        )
    return specialty


# UPDATE
@router.patch(
    "/{specialty_id}",
    response_model=SpecialtyRead,
    summary="Update specialty",
)
async def update_specialty_by_id_handle(
    specialty_id: int,
    specialty_data: SpecialtyUpdate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> SpecialtyRead:
    updated_specialty = await update_specialty(specialty_id, specialty_data, db, redis)
    if updated_specialty is None:
        logger.warning(
            "Specialty with id {specialty_id} not found",
            specialty_id=specialty_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Specialty not found"
        )
    return updated_specialty


# DELETE
@router.delete(
    "/{specialty_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete specialty",
)
async def delete_specialty_handle(
    specialty_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> None:
    deleted_specialty = await delete_specialty(specialty_id, db, redis)
    if not deleted_specialty:
        logger.info(
            "A specialty with this id does not exist: {specialty_id}",
            specialty_id=specialty_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A specialty with this id does not exist: {specialty_id}",
        )
