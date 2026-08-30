import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import ReviewStatus
from src.core.schemas import PaginationParams


class ReviewCreate(BaseModel):
    doctor_id: int
    rating: int = Field(ge=1, le=5)
    comment: str = Field(max_length=350)


class ReviewRead(BaseModel):
    id: int
    user_id: int
    doctor_id: int
    rating: int
    comment: str
    status: ReviewStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewFilterParams(PaginationParams):
    rating: int | None = Field(default=None, ge=1, le=5)
    is_positive: bool | None = Field(default=None)
    status: ReviewStatus
