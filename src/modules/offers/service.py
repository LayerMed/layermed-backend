from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.models import Offer
from src.modules.offers.schemas import OfferCreate, OfferRead
from src.core.redis import RedisCache


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

    