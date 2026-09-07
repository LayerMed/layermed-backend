import asyncio

from fastapi import UploadFile
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.storage.s3 import delete_image
from src.services.images.service import offer_optimization, save_and_upload_image
from src.common.enums import CacheTTL, ModerationStatus, S3Folders, UserRole
from src.services.storage.redis import RedisCache
from src.common.schemas import PaginatedResponse
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.exceptions import (
    OfferAccessDenied,
    OfferImagesCountError,
    OfferImagesError,
    OfferNotFoundError,
)
from src.modules.offers.models import Offer
from src.modules.offers.schemas import (
    OfferCreate,
    OfferFilterParams,
    OfferRead,
    OfferUpdate,
)
from src.modules.users.schemas import UserRead


# CREATE
async def create_offer(
    new_offer: OfferCreate,
    current_doctor: DoctorRead,
    db: AsyncSession,
    redis: RedisCache,
) -> OfferRead:
    offer_data = new_offer.model_dump()
    query = (
        insert(Offer)
        .values(
            doctor_id=current_doctor.id,
            images=[],
            **offer_data,
        )
        .returning(Offer)
    )
    result = await db.execute(query)
    created_offer = result.scalar_one()

    await db.commit()
    await redis.invalidate("offers")

    return OfferRead.model_validate(created_offer)


async def upload_offer_images(
    images: list[UploadFile],
    offer_id: int,
    current_doctor: DoctorRead,
    db: AsyncSession,
    redis: RedisCache,
) -> list[str]:
    offer = await db.get(Offer, offer_id)

    if not offer:
        raise OfferNotFoundError()
    if offer.doctor_id != current_doctor.id:
        raise OfferAccessDenied()
    current_images = offer.images or []
    if len(current_images) + len(images) > 10:
        raise OfferImagesCountError()

    try:
        tasks = [
            save_and_upload_image(image, S3Folders.OFFERS, offer_optimization)
            for image in images
        ]
        keys = await asyncio.gather(*tasks, return_exceptions=True)
        uploaded_keys = []
        has_errors = False

        for key in keys:
            if isinstance(key, Exception):
                has_errors = True
            else:
                uploaded_keys.append(key)

        if has_errors:
            if uploaded_keys:
                await asyncio.gather(*[delete_image(k) for k in uploaded_keys])
            raise OfferImagesError()

        try:
            stmt = (
                update(Offer)
                .where(Offer.id == offer_id)
                .values(images=Offer.images.concat(uploaded_keys))
                .returning(Offer.images)
            )
            result = await db.execute(stmt)
            offer.images = result.scalar_one()
            await db.commit()
        except Exception:
            await db.rollback()
            await asyncio.gather(*[delete_image(k) for k in uploaded_keys])
            raise

        await asyncio.gather(
            redis.invalidate(f"offers:items:{offer_id}"),
            redis.invalidate("offers:list:default"),
            return_exceptions=True,
        )
        return offer.images

    finally:
        await asyncio.gather(*[img.close() for img in images])


# READ
async def get_offers_by_filters(
    current_user: UserRead | None,
    filters: OfferFilterParams,
    db: AsyncSession,
    redis: RedisCache,
) -> PaginatedResponse[OfferRead]:
    is_admin = current_user and current_user.role == UserRole.ADMIN
    is_default = filters.is_default_page(is_admin=bool(is_admin))

    cache_key = redis.build_key("offers", "list", "default")
    if is_default:
        cached = await redis.getc(cache_key)
        if cached:
            return PaginatedResponse[OfferRead].model_validate(cached)

    query = select(Offer)

    if is_admin:
        if filters.status is not None:
            query = query.filter(Offer.status == filters.status)
    else:
        query = query.filter(Offer.status == ModerationStatus.APPROVED)

    if filters.city_id:
        query = query.filter(Offer.city_id == filters.city_id)
    if filters.cost:
        query = query.filter(Offer.cost <= filters.cost)
    if filters.offer_format:
        offer_format = filters.offer_format
        query = query.filter(Offer.offer_format == offer_format)
    if filters.doctor_experience_years or filters.doctor_rating_avg:
        query = query.join(Offer.doctor)
        if filters.doctor_experience_years:
            query = query.where(
                Doctor.experience_years >= filters.doctor_experience_years
            )
        if filters.doctor_rating_avg:
            query = query.where(Doctor.rating_avg >= filters.doctor_rating_avg)

    query = query.limit(filters.limit).offset(filters.offset)
    result = await db.execute(query)
    offers = result.scalars().all()

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = (await db.execute(count_query)).scalar_one()

    offers_dto = PaginatedResponse[OfferRead](
        items=[OfferRead.model_validate(u) for u in offers],
        limit=filters.limit,
        offset=filters.offset,
        total=total,
    )

    if is_default:
        await redis.setc(cache_key, offers_dto, CacheTTL.FAST)

    return offers_dto


async def get_offers_by_doctor(
    current_doctor: DoctorRead, 
    db: AsyncSession,    
) -> list[OfferRead]:
    query = (
        select(Offer)
        .where(Offer.doctor_id == current_doctor.id)
    )
    result = await db.execute(query)
    offers = result.scalars().all()

    if not offers:
        raise OfferNotFoundError()

    return [OfferRead.model_validate(offer) for offer in offers] 


async def get_offer_by_id(
    offer_id: int,
    db: AsyncSession,
    redis: RedisCache,
) -> OfferRead:
    cache_key = redis.build_key("offers", "items", offer_id)

    cached_offer = await redis.getc(cache_key)
    if cached_offer:
        return OfferRead.model_validate(cached_offer)

    offer = await db.get(Offer, offer_id)
    if not offer:
        raise OfferNotFoundError()

    offer_dto = OfferRead.model_validate(offer)

    if offer.status == ModerationStatus.APPROVED:
        await redis.setc(cache_key, offer_dto, ex=CacheTTL.SLOW)

    return offer_dto
       

# UPDATE
async def update_offer_by_id(
    offer_id: int,
    offer_data: OfferUpdate,
    db: AsyncSession,
    redis: RedisCache,
) -> OfferRead:
    update_data = offer_data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_offer_by_id(offer_id, db, redis)

    offer = await db.get(Offer, offer_id)
    if not offer:
        raise OfferNotFoundError()

    images_to_delete = []

    if "images" in update_data:
        old_images = set(offer.images)
        new_images = set(offer_data.images or [])
        images_to_delete = list(old_images - new_images)

    for field, value in update_data.items():
        setattr(offer, field, value)

    offer.status = ModerationStatus.PENDING

    if "images" in update_data:
        flag_modified(offer, "images")

    await db.commit()
    await db.refresh(offer)

    if images_to_delete:
        await asyncio.gather(
            *[delete_image(key) for key in images_to_delete],
            return_exceptions=True,
        )
    
    await redis.invalidate("offers")

    return OfferRead.model_validate(offer)


# DELETE
async def delete_offer(
    offer_id: int,
    current_doctor: DoctorRead,
    db: AsyncSession,
    redis: RedisCache,
) -> None:
    query = select(Offer).where(Offer.id == offer_id)
    result = await db.execute(query)
    offer = result.scalar_one_or_none()

    if offer is None:
        raise OfferNotFoundError()

    if offer.doctor_id != current_doctor.id:
        raise OfferAccessDenied()

    await db.delete(offer)
    await db.commit()
    await redis.invalidate("offers:items")
