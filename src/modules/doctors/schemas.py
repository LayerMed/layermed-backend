import datetime

from pydantic import BaseModel, ConfigDict


class DoctorRegister(BaseModel):
    specialty_id: int
    education: str
    experience_years: int
    bio: str

    model_config = ConfigDict(from_attributes=True)


class DoctorRead(BaseModel):
    id: int
    user_id: int
    specialty_id: int
    education: str
    experience_years: int
    bio: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class DoctorUpdate(BaseModel):
    specialty_id: int | None = None
    education: str | None = None
    experience_years: int | None = None
    bio: str | None = None
