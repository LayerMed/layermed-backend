import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from src.core.security import BAD_PASSWORDS


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
    email: EmailStr
    role: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RegisterUser(BaseModel):
    email: EmailStr
    password: ValidPassword
    name: str
    birth_date: datetime.date | None = None


class UserPasswordChange(BaseModel):
    old_password: str
    new_password: ValidPassword


class PasswordConfirm(BaseModel):    
    password: str


class UserUpdate(BaseModel):
    name: str | None = None
    birth_date: datetime.date | None = None