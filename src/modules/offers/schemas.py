from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import ModerationStatus, OfferFormat


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


class OfferFilterParams(BaseModel):
    city_id: int | None = None
    cost: int | None = None
    status: ModerationStatus | None = None
    offer_format: OfferFormat | None = None

    doctor_experience_years: int | None = Field(default=None, ge=0)
    doctor_rating_avg: int | None = Field(default=None, ge=0, le=5)

    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(from_attributes=True)


class OfferUpdate(BaseModel):
    city_id: int | None = None
    title: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, min_length=2, max_length=500)
    cost: int | None = Field(default=None, gt=0)
    offer_format: OfferFormat | None = None
    images: list[str] | None = None


class OfferReject(BaseModel):
    rejection_reason: str | None = Field(default=None, max_length=255)
