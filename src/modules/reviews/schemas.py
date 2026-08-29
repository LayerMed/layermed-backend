import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    doctor_id: int
    rating: int = Field(ge=1, le=5)
    comment: str = Field(max_length=350)


class ReviewRead(BaseModel):
    user_id: int
    doctor_id: int
    rating: int
    comment: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ВЫНЕСТИ ЭТО В SRC
class PaginationParams(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ReviewFilterParams(PaginationParams):
    rating: int | None = Field(default=None, ge=1, le=5)
    is_positive: bool | None = Field(default=None)


class ReviewPaginatedResponse(BaseModel):
    items: list[ReviewRead]
    total: int
    limit: int
    offset: int
