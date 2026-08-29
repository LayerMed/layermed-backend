from typing import Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordConfirm(BaseModel):
    password: str


class PaginationParams(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]    
    limit: int
    offset: int