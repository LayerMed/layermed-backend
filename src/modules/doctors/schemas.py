import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.common.enums import ModerationStatus, TextLength
from src.common.schemas import BaseFilterParams
from src.modules.specialties.schemas import SpecialtyRead

ValidBio = Annotated[str, Field(max_length=TextLength.MEDIUM)]

class DoctorCreate(BaseModel):
    specialty_ids: list[int] = Field(default_factory=list)
    education: str
    degree: str
    experience_years: int
    bio: ValidBio | None
    clinic: str
    avatar_url: str | None = None


class DoctorRead(BaseModel):
    id: int
    user_id: int
    education: str
    degree: str | None = None
    experience_years: int
    bio: ValidBio
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
    bio: ValidBio | None = None


class DoctorFilterParams(BaseFilterParams):
    experience_years: int | None = Field(default=None, ge=0)
    max_price: int | None = None
    rating_avg: float | None = Field(default=None, ge=0, le=5)
    status: ModerationStatus | None = None


class DoctorReject(BaseModel):
    rejection_reason: str = Field(max_length=255)
