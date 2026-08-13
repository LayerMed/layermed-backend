import datetime

from pydantic import BaseModel, ConfigDict


class CityRead(BaseModel):
    id: int
    name: str    
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CityCreate(BaseModel):
    name: str


class CityUpdate(BaseModel):
    name: str | None = None

