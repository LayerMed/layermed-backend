import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.core.security import BAD_PASSWORDS


class UserRead(BaseModel):
    id: int
    name: str
    birth_date: datetime.date | None = None
    email: EmailStr
    role: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


def validate_password_rules(value: str) -> str:
    if value in BAD_PASSWORDS:
        raise ValueError("This password is too easy. Please, use other password")
    if len(set(value)) == 1:
        raise ValueError("Password cannot consist of a single repeating character")
    return value


class Password(BaseModel):
    password: str = Field(min_length=8, max_length=16)

    @field_validator("password")
    @classmethod
    def check_pwd(cls, value: str) -> str:
        return validate_password_rules(value)


class UserPasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=16)

    @field_validator("new_password")
    @classmethod
    def check_new_pwd(cls, value: str) -> str:
        return validate_password_rules(value)


class RegisterUser(UserLogin):
    name: str
    birth_date: datetime.date | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    birth_date: datetime.date | None = None