from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.schemas import PaginatedResponse
from src.modules.doctors.models import Doctor
from src.core.enums import ModerationStatus, UserRole
from src.modules.users.schemas import UserRead
from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.models import Offer
from src.modules.offers.schemas import OfferCreate, OfferFilterParams, OfferRead
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