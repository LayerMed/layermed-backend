
import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserRead(BaseModel):
    id: int
    name: str
    age: datetime.date | None = None
    email: EmailStr
    role: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str