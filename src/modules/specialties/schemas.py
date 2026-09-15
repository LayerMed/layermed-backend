import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.common.enums import TextLength

SpecialtyName = Annotated[str, Field(min_length=2, max_length=TextLength.SHORT)]
SpecialtyDescription = Annotated[str, Field(min_length=8, max_length=TextLength.LONG)]


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


class SpecialtyUpdate(BaseModel):
    name: SpecialtyName | None = None
    description: SpecialtyDescription | None = None


class SpecialtyCountRead(BaseModel):
    id: int
    name: str
    doctors_count: int

    model_config = ConfigDict(from_attributes=True)
