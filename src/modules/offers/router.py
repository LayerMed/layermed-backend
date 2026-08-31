

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.users.schemas import UserRead
from src.core.schemas import PaginatedResponse
from src.core.database import get_session
from src.core.dependencies import get_current_doctor, get_optional_user
from src.core.redis import RedisCache, get_redis
from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.schemas import OfferCreate, OfferFilterParams, OfferRead
from src.modules.offers.service import create_offer, get_all_offers, get_offer_by_id


router = APIRouter(prefix='/offers', tags=["Offers"])


# CREATE
@router.post(
    "/",
    response_model=OfferRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create offer"
)
async def create_offer_handle(
    new_offer: OfferCreate,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis)
) -> OfferRead:
    return await create_offer(new_offer, current_doctor, db, redis)


# READ
@router.get(
    "/",
    response_model=PaginatedResponse[OfferRead],
    summary="Get all offers"
)
async def get_all_offers_handle(    
    filters: Annotated[OfferFilterParams, Depends()],
    current_user: UserRead | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis) 
) -> PaginatedResponse[OfferRead]:
    return await get_all_offers(current_user, filters, db, redis)


@router.get(
    "/{offer_id}",
    response_model=OfferRead,
    summary="Get offer by id"
)
async def get_offer_by_id_handle(
    offer_id: int,
    current_user: UserRead | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis) 
) -> OfferRead:
    return await get_offer_by_id(offer_id, current_user, db, redis)

