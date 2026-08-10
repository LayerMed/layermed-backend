from fastapi import Depends, HTTPException, status
import jwt
from src.core.enums import UserRole
from src.modules.users.models import User
from src.modules.users.service import get_user_by_email
from src.core.config import settings
from src.core.security import oauth2_scheme
from src.core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials or token expired",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_session)
):
    try:
        payload = jwt.decode(token, settings.KEY, algorithms=settings.ALGORITHM)
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = await get_user_by_email(email, db)
    if user is None:
        raise credentials_exception

    return user


async def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have enough permissions. Admin only!",
        )
    return current_user
