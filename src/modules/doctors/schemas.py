import datetime

from pydantic import BaseModel, ConfigDict, Field


class DoctorCreate(BaseModel):
    specialty_ids: list[int] = Field(default_factory=list)
    education: str
    experience_years: int
    bio: str


class DoctorRead(BaseModel):
    id: int
    user_id: int
    specialty_ids: list[int] = Field(default_factory=list)
    education: str
    experience_years: int
    bio: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class DoctorUpdate(BaseModel):
    specialty_ids: list[int] | None = None
    education: str | None = None
    experience_years: int | None = None
    bio: str | None = None


class DoctorFilterParams(BaseModel):
    specialty_id: int | None = None
    min_experience: int | None = Field(default=None, ge=0)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
