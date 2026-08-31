from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.enums import ModerationStatus, OfferFormat

class OfferCreate(BaseModel):
    city_id: int
    title: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=2, max_length=500)
    cost: int = Field(gt=0)    
    offer_format: OfferFormat
    images: list[str] | None = None    


class OfferRead(BaseModel):
    doctor_id: int
    city_id: int
    title: str
    description: str
    cost: int
    status: ModerationStatus
    offer_format: OfferFormat
    images: list[str] | None

    model_config = ConfigDict(from_attributes=True)
