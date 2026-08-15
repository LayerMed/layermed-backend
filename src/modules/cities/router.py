from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user
from src.core.logs import logger
from src.modules.cities.schemas import CityCreate, CityRead, CityUpdate
from src.modules.cities.service import (
    create_city,
    delete_city,
    get_cities,
    get_city_by_id,
    update_city,
)
from src.modules.users.models import User

router = APIRouter(prefix="/cities", tags=["Cities"])


# ADMIN
@router.post(
    "/",
    response_model=CityRead,
    summary="Create city",
    status_code=status.HTTP_201_CREATED,
    description="Create city in database",
)
async def create_city_handle(
    new_city: CityCreate,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    created_city = await create_city(new_city, db)
    if created_city is None:
        logger.warning("City with this name: {name} already exists", name=new_city.name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="City with this name already exists",
        )
    return created_city


# READ
@router.get(
    "/",
    response_model=list[CityRead],
    summary="Get all cities",
    description="Get all cities from database",
)
async def get_cities_handle(
    db: AsyncSession = Depends(get_session),
):
    cities = await get_cities(db)
    return cities


@router.get(
    "/{city_id}",
    response_model=CityRead,
    summary="Get city by id",
    description="Get one city from database via id",
)
async def get_city_by_id_handle(city_id: int, db: AsyncSession = Depends(get_session)):
    city = await get_city_by_id(city_id, db)
    if city is None:
        logger.warning(
            "Failed to fetch city: City with id {city_id} not found",
            city_id=city_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="City not found"
        )

    return city


# UPDATE
@router.patch(
    "/{city_id}",
    response_model=CityRead,
    summary="Update city",
    description="Update city in database",
)
async def update_city_by_id_handle(
    city_id: int,
    city_data: CityUpdate,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    updated_city = await update_city(city_id, city_data, db)
    if updated_city is None:
        logger.warning(
            "Failed to fetch city: City with id {city_id} not found",
            city_id=city_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="City not found"
        )
    return updated_city


# DELETE
@router.delete(
    "/{city_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete city",
    description="Delete city from database",
)
async def delete_city_handle(
    city_id: int,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    deleted_city = await delete_city(city_id, db)
    if deleted_city is None:
        logger.info("A city with this id does not exist: {city_id}", city_id=city_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A city with this id does not exist: {city_id}",
        )
    return deleted_city
