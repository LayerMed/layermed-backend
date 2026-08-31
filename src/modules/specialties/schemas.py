import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

SpecialtyName = Annotated[str, Field(min_length=2, max_length=50)]
SpecialtyDescription = Annotated[str, Field(min_length=8, max_length=100)]


class SpecialtyCreate(BaseModel):
    name: SpecialtyName
    description: SpecialtyDescription


class SpecialtyRead(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class SpecialtyCountRead(BaseModel):
    id: int
    name: str
    doctors_count: int

    model_config = ConfigDict(from_attributes=True)


class SpecialtyUpdate(BaseModel):
    name: SpecialtyName | None = None
    description: SpecialtyDescription | None = None
