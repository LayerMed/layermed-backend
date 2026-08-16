import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

SymptomName = Annotated[str, Field(min_length=2, max_length=50)]
SymptomDescription = Annotated[str, Field(min_length=8, max_length=100)]


class SymptomCreate(BaseModel):
    name: SymptomName
    description: SymptomDescription


class SymptomRead(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class SymptomUpdate(BaseModel):
    name: SymptomName | None = None
    description: SymptomDescription | None = None
