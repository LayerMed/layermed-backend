import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field
from src.core.security import BAD_PASSWORDS

from src.core.enums import UserRole


def validate_password_rules(value: str) -> str:
    if value in BAD_PASSWORDS:
        raise ValueError("This password is too easy. Please, use another password")
    if len(set(value)) == 1:
        raise ValueError("Password cannot consist of a single repeating character")
    return value


ValidPassword = Annotated[
    str,
    Field(min_length=8, max_length=16),
    AfterValidator(validate_password_rules),
]


class UserRead(BaseModel):
    id: int
    name: str
    birth_date: datetime.date | None = None
    city_id: int | None = None
    email: EmailStr
    role: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class UserFilterParams(BaseModel):
    name: str | None = None
    birth_date: datetime.date | None = None
    city_id: int | None = None
    email: str | None = None
    role: UserRole | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RegisterUser(BaseModel):
    name: str
    city_id: int | None = Field(default=None)
    birth_date: datetime.date | None = None
    email: EmailStr
    password: ValidPassword


class UserPasswordChange(BaseModel):
    old_password: str
    new_password: ValidPassword


class PasswordConfirm(BaseModel):
    password: str


class UserUpdate(BaseModel):
    birth_date: datetime.date | None = None
    city_id: int | None = None
    name: str | None = None
