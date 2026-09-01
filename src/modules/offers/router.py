from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.offers.models import Offer
from src.core.moderation.service import approve_item, reject_item
from src.core.database import get_session
from src.core.dependencies import get_admin_user, get_current_doctor, get_optional_user
from src.core.redis import RedisCache, get_redis
from src.core.schemas import PaginatedResponse
from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.schemas import (
    OfferCreate,
    OfferFilterParams,
    OfferRead,
    OfferReject,
    OfferUpdate,
)
from src.modules.offers.service import (    
    create_offer,
    delete_offer,
    get_all_offers,
    get_offer_by_id,    
    update_offer_by_id,
)
from src.modules.users.schemas import UserRead

router = APIRouter(prefix="/offers", tags=["Offers"])


# CREATE
@router.post(
    "/",
    response_model=OfferRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create offer",
)
async def create_offer_handle(
    new_offer: OfferCreate,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> OfferRead:
    return await create_offer(new_offer, current_doctor, db, redis)


# READ
@router.get("/", response_model=PaginatedResponse[OfferRead], summary="Get all offers")
async def get_all_offers_handle(
    filters: Annotated[OfferFilterParams, Depends()],
    current_user: UserRead | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> PaginatedResponse[OfferRead]:
    return await get_all_offers(current_user, filters, db, redis)


@router.get("/{offer_id}", response_model=OfferRead, summary="Get offer by id")
async def get_offer_by_id_handle(
    offer_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> OfferRead:
    return await get_offer_by_id(offer_id, db, redis)


# UPDATE
@router.patch("/{offer_id}", response_model=OfferRead, summary="Update offer by id")
async def update_offer_by_id_handle(
    offer_id: int,
    offer_data: OfferUpdate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> OfferRead:
    return await update_offer_by_id(offer_id, offer_data, db, redis)


@router.patch(
    "/{offer_id}/approve",
    response_model=OfferRead,
    summary="Approve offer application (Admin only)",
)
async def approve_offer_handle(
    offer_id: int,
    admin: UserRead = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> OfferRead:
    return await approve_item(Offer, OfferRead, offer_id, db ,redis, "doctors")


@router.patch(
    "/{offer_id}/reject",
    response_model=OfferRead,
    summary="Reject offer application (Admin only)",
)
async def reject_offer_handle(
    offer_id: int,
    reject_data: OfferReject,
    admin: UserRead = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> OfferRead:
    return await reject_item(Offer, OfferRead, offer_id, db, redis, "offers")


# DELETE
@router.delete(
    "/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete offer",
)
async def delete_offer_handle(
    offer_id: int,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> None:
    await delete_offer(offer_id, current_doctor, db, redis)
