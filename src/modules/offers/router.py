from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.enums import RateLimit
from src.common.schemas import PaginatedResponse
from src.core.dependencies import get_admin_user, get_current_doctor, get_optional_user
from src.core.limiter import limiter
from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.models import Offer
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
    delete_offer_image,
    get_offer_by_id,
    get_offers_by_doctor,
    get_offers_by_filters,
    update_offer_by_id,
    upload_offer_images,
)
from src.modules.users.schemas import UserRead
from src.services.moderation.service import approve_item, reject_item
from src.services.storage.postgres import get_session
from src.services.storage.redis import RedisCache, get_redis

router = APIRouter(prefix="/offers", tags=["Offers"])


# CREATE
@router.post(
    "/",
    response_model=OfferRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create offer",
)
@limiter.limit(RateLimit.MUTATION)
async def create_offer_handle(
    request: Request,
    new_offer: OfferCreate,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> OfferRead:
    return await create_offer(new_offer, current_doctor, db, redis)


@router.post(
    "/{offer_id}/images",
    response_model=list[str],
    status_code=status.HTTP_201_CREATED,
    summary="Upload images for doctor offer",
)
@limiter.limit(RateLimit.MUTATION)
async def upload_offer_images_handle(
    request: Request,
    offer_id: int,
    images: list[UploadFile] = File(...),
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> list[str]:
    return await upload_offer_images(images, offer_id, current_doctor, db, redis)


# READ
@router.get("/", response_model=PaginatedResponse[OfferRead], summary="Get all offers")
@limiter.limit(RateLimit.BURST)
async def get_offers_by_filters_handle(
    request: Request,
    filters: Annotated[OfferFilterParams, Depends()],
    optional_user: UserRead | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> PaginatedResponse[OfferRead]:
    return await get_offers_by_filters(optional_user, filters, db, redis)


@router.get(
    "/doctor",
    response_model=list[OfferRead],
    summary="Get all offers from current doctor",
)
@limiter.limit(RateLimit.READ)
async def get_offers_by_doctor_handle(
    request: Request,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
) -> list[OfferRead]:
    return await get_offers_by_doctor(current_doctor, db)


@router.get("/{offer_id}", response_model=OfferRead, summary="Get offer by id")
@limiter.limit(RateLimit.READ)
async def get_offer_by_id_handle(
    request: Request,
    offer_id: int,
    optional_user: UserRead | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> OfferRead:
    return await get_offer_by_id(offer_id, optional_user, db, redis)


# UPDATE
@router.patch("/{offer_id}", response_model=OfferRead, summary="Update offer by id")
@limiter.limit(RateLimit.MUTATION)
async def update_offer_by_id_handle(
    request: Request,
    offer_id: int,
    offer_data: OfferUpdate,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> OfferRead:
    return await update_offer_by_id(offer_id, offer_data, current_doctor, db, redis)


@router.patch(
    "/{offer_id}/approve",
    response_model=OfferRead,
    summary="Approve offer application (Admin only)",
)
async def approve_offer_handle(
    offer_id: int,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: UserRead = Depends(get_admin_user),
) -> OfferRead:
    return await approve_item(Offer, OfferRead, offer_id, db, redis, "offers")


@router.patch(
    "/{offer_id}/reject",
    response_model=OfferRead,
    summary="Reject offer application (Admin only)",
)
async def reject_offer_handle(
    offer_id: int,
    reject_data: OfferReject,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
    admin: UserRead = Depends(get_admin_user),
) -> OfferRead:
    return await reject_item(
        Offer,
        OfferRead,
        offer_id,
        db,
        redis,
        reject_data.rejection_reason,
        "offers",
    )


# DELETE
@router.delete(
    "/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete offer",
)
@limiter.limit(RateLimit.MUTATION)
async def delete_offer_handle(
    request: Request,
    offer_id: int,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> None:
    await delete_offer(offer_id, current_doctor, db, redis)


@router.delete(
    "/{offer_id}/images/{image_key:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete image from offer",
)
@limiter.limit(RateLimit.MUTATION)
async def delete_offer_image_handle(
    request: Request,
    offer_id: int,
    image_key: str,
    current_doctor: DoctorRead = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> None:
    await delete_offer_image(offer_id, image_key, current_doctor, db, redis)
