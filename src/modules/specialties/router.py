from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.enums import RateLimit
from src.core.dependencies import get_admin_user
from src.core.limiter import limiter
from src.modules.specialties.schemas import (
    SpecialtyCountRead,
    SpecialtyCreate,
    SpecialtyRead,
    SpecialtyUpdate,
)
from src.modules.specialties.service import (
    create_specialty,
    delete_specialty,
    get_specialties,
    get_specialties_count,
    get_specialty_by_id,
    update_specialty,
)
from src.modules.users.models import User
from src.services.storage.postgres import get_session
from src.services.storage.redis import RedisCache, get_redis

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
    return created_specialty


# READ
@router.get(
    "/",
    response_model=list[SpecialtyRead],
    summary="Get all specialties",
)
@limiter.limit(RateLimit.BURST)
async def get_specialties_handle(
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> list[SpecialtyRead]:
    specialties = await get_specialties(db, redis)
    return specialties


@router.get(
    "/count",
    response_model=list[SpecialtyCountRead],
    summary="Get numbers of specialties",
)
@limiter.limit(RateLimit.BURST)
async def get_specialties_count_handle(
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> list[SpecialtyCountRead]:
    return await get_specialties_count(db, redis)


@router.get(
    "/{specialty_id}",
    response_model=SpecialtyRead,
    summary="Get specialty by id",
)
@limiter.limit(RateLimit.READ)
async def get_specialty_by_id_handle(
    request: Request,
    specialty_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> SpecialtyRead:
    specialty = await get_specialty_by_id(specialty_id, db, redis)
    return specialty


# UPDATE
@router.patch(
    "/{specialty_id}",
    response_model=SpecialtyRead,
    summary="Update specialty",
)
@limiter.limit(RateLimit.MUTATION)
async def update_specialty_by_id_handle(
    request: Request,
    specialty_id: int,
    specialty_data: SpecialtyUpdate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> SpecialtyRead:
    updated_specialty = await update_specialty(specialty_id, specialty_data, db, redis)
    return updated_specialty


# DELETE
@router.delete(
    "/{specialty_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete specialty",
)
@limiter.limit(RateLimit.MUTATION)
async def delete_specialty_handle(
    request: Request,
    specialty_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: User = Depends(get_admin_user),
) -> None:
    await delete_specialty(specialty_id, db, redis)
