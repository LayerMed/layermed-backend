from typing import Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordConfirm(BaseModel):
    password: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]    
    limit: int 
    offset: int


class BaseFilterParams(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    def is_default_page(self, is_admin: bool = False) -> bool:
        if is_admin:
            return False
        
        filters_applied = self.model_dump(
            exclude_unset=True, 
            exclude_none=True,
            exclude={"limit", "offset", "total"}
        )

        return not filters_applied and self.offset == 0 and self.limit == 10