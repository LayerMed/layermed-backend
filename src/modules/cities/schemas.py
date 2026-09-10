import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.common.enums import TextLength


CityName = Annotated[str, Field(max_length=TextLength.SHORT)]


class CityCreate(BaseModel):
    name: CityName


class CityRead(BaseModel):
    id: int
    name: CityName
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CityUpdate(BaseModel):
    name: CityName | None = None
