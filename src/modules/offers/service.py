from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.offers.exceptions import OfferAccessDenied, OfferNotFoundError
from src.core.schemas import PaginatedResponse
from src.modules.doctors.models import Doctor
from src.core.enums import CacheTTL, ModerationStatus, UserRole
from src.modules.users.schemas import UserRead
from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.models import Offer
from src.modules.offers.schemas import OfferCreate, OfferFilterParams, OfferRead, OfferUpdate
from src.core.redis import RedisCache


# CREATE
async def create_offer(
    new_offer: OfferCreate,
    current_doctor: DoctorRead,
    db: AsyncSession,
    redis: RedisCache,
) -> OfferRead:
    query = (
        insert(Offer)
        .values(
            doctor_id=current_doctor.id,
            **new_offer.model_dump()
        )
        .returning(Offer)
    )
    result = await db.execute(query)
    created_offer = result.scalar_one()

    await db.commit()
    await redis.invalidate("offers")

    return OfferRead.model_validate(created_offer)


# READ
async def get_all_offers(    
    current_user: UserRead | None,
    filters: OfferFilterParams,
    db: AsyncSession,
    redis: RedisCache,
) -> PaginatedResponse[OfferRead]:
    is_admin = current_user and current_user.role == UserRole.ADMIN
    # cache_key = redis.build_key("offers", "items", "all")
    # cached_offers = await redis.getc(cache_key)
    # if cached_offers:
    # Сделать кеш везде где есть offset и limit. добавить total
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
            query = query.where(Doctor.experience_years >= filters.doctor_experience_years)
        if filters.doctor_rating_avg:
            query = query.where(Doctor.rating_avg >= filters.doctor_rating_avg)

    query = query.limit(filters.limit).offset(filters.offset)
    result = await db.execute(query)
    offers = result.scalars().all()

    return PaginatedResponse[OfferRead](
        items=[OfferRead.model_validate(u) for u in offers],
        limit=filters.limit,
        offset=filters.offset,
    )


async def get_offer_by_id(
    offer_id: int,
    db: AsyncSession,
    redis: RedisCache,
) -> OfferRead:
    cache_key = redis.build_key("offers", "items", offer_id)
    
    cached_offer = await redis.getc(cache_key)
    if cached_offer:
        return OfferRead.model_validate(cached_offer)
    
    query = select(Offer).where(Offer.id == offer_id)
    result = await db.execute(query)
    offer = result.scalar_one_or_none()

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

    query = (
        update(Offer)
        .where(Offer.id == offer_id)
        .values(
            **update_data, 
            status=ModerationStatus.PENDING
        )
        .returning(Offer)
    )
    result = await db.execute(query)
    updated_offer = result.scalar_one()

    await db.commit()
    await redis.invalidate("offers")

    return OfferRead.model_validate(updated_offer)


# ВЫНЕСТИ ЛОГИКУ МОДЕРАЦИИ ИЗ DOCTORS , REVIEWS И OFFERS В ОТДЕЛЬНЫЙ МОДУЛЬ
async def update_offer_status(
    offer_id: int, 
    status: ModerationStatus,
    db: AsyncSession,
    redis: RedisCache,
    rejection_reason: str | None = None
) -> OfferRead:
    query = (
        update(Offer)
        .where(Offer.id == offer_id)
        .values(status=status, rejection_reason=rejection_reason)
        .returning(Offer)
    )
    result = await db.execute(query)
    updated_offer = result.scalar_one_or_none()

    if updated_offer is None:
        raise OfferNotFoundError()

    await db.commit()
    await redis.invalidate("offers")
    return OfferRead.model_validate(updated_offer)


async def approve_offrer(
    offer_id: int,
    db: AsyncSession,
    redis: RedisCache,
) -> OfferRead:
    return await update_offer_status(
        offer_id, ModerationStatus.APPROVED, db, redis, rejection_reason=None
    )


async def reject_offrer(
    offer_id: int,
    rejection_reason: str | None,
    db: AsyncSession,
    redis: RedisCache,
) -> OfferRead:
    return await update_offer_status(
        offer_id, ModerationStatus.REJECTED, db, redis, rejection_reason=rejection_reason
    )


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
    await redis.invalidate("offers")