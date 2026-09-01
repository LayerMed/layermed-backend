import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import ModerationStatus
from src.core.schemas import PaginationParams
from src.modules.specialties.schemas import SpecialtyRead


class DoctorCreate(BaseModel):
    specialty_ids: list[int] = Field(default_factory=list)
    education: str
    degree: str
    experience_years: int
    bio: str
    clinic: str
    avatar_url: str | None = None


class DoctorRead(BaseModel):
    id: int
    user_id: int
    education: str
    degree: str | None = None
    experience_years: int
    bio: str
    min_price: int
    clinic: str
    avatar_url: str | None = None
    rating_avg: float
    reviews_count: int
    status: ModerationStatus
    rejection_reason: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class DoctorReadDetailed(DoctorRead):
    specialties: list[SpecialtyRead] = Field(default_factory=list)


class DoctorUpdate(BaseModel):
    specialty_ids: list[int] | None = None
    education: str | None = None
    experience_years: int | None = None
    bio: str | None = None


class DoctorFilterParams(PaginationParams):
    specialty_id: int | None = (
        None  # переиминовать в связи с изменением логики специальностей
    )
    experience_years: int | None = Field(default=None, ge=0)
    max_price: int | None = None
    rating_avg: int | None = Field(default=None, ge=0, le=5)
    status: ModerationStatus | None = None


class DoctorReject(BaseModel):
    rejection_reason: str = Field(max_length=255)
