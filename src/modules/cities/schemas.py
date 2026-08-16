import datetime

from pydantic import BaseModel, ConfigDict, Field


class CityCreate(BaseModel):
    name: str = Field(min_length=2)


class CityRead(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CityUpdate(BaseModel):
    name: str | None = None
