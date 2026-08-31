from datetime import UTC, datetime, timedelta

import jwt
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from src.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login", auto_error=False)


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
