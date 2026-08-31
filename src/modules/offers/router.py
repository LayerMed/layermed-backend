

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_current_doctor
from src.core.redis import RedisCache, get_redis
from src.modules.doctors.schemas import DoctorRead
from src.modules.offers.schemas import OfferCreate, OfferRead
from src.modules.offers.service import create_offer


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


