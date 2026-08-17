from datetime import UTC, datetime, timedelta

import jwt
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.users.schemas import UserRead
from src.modules.users.models import User
from src.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


with open("src/core/bad_passwords.txt", encoding="utf-8") as f:
    BAD_PASSWORDS = set(f.read().splitlines())


def hash_pwd(pwd: str) -> str:
    return pwd_context.hash(pwd)


def verify_pwd(plain_pwd: str, hashed_pwd: str) -> bool:
    return pwd_context.verify(plain_pwd, hashed_pwd)


def create_access_token(user_data: dict) -> str:
    data_copy = user_data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.TOKEN_EXPIRE)
    data_copy.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(data_copy, settings.KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_user_password(current_user: UserRead,  db: AsyncSession):
    query_password = select(User.password).filter(User.id == current_user.id)
    result_password = await db.execute(query_password)
    current_password = result_password.scalar_one_or_none()
    return current_password



