from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import ModerationStatus, OfferFormat
from src.core.schemas import BaseFilterParams


class OfferCreate(BaseModel):
    city_id: int
    title: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=2, max_length=500)
    cost: int = Field(gt=0)
    offer_format: OfferFormat
    images: list[str] | None = None


class OfferRead(BaseModel):
    id: int
    doctor_id: int
    city_id: int
    title: str
    description: str
    cost: int
    status: ModerationStatus
    offer_format: OfferFormat
    images: list[str] | None

    model_config = ConfigDict(from_attributes=True)


class OfferFilterParams(BaseFilterParams):
    city_id: int | None = None
    cost: int | None = None
    status: ModerationStatus | None = None
    offer_format: OfferFormat | None = None

    doctor_experience_years: int | None = Field(default=None, ge=0)
    doctor_rating_avg: int | None = Field(default=None, ge=0, le=5)

    model_config = ConfigDict(from_attributes=True)


class OfferUpdate(BaseModel):
    city_id: int | None = None
    title: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, min_length=2, max_length=500)
    cost: int | None = Field(default=None, gt=0)
    offer_format: OfferFormat | None = None
    images: list[str] | None = None


class OfferReject(BaseModel):
    rejection_reason: str = Field(max_length=255)
