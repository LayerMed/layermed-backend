import jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from src.core.config import settings
from src.core.database import get_session
from src.core.enums import UserRole
from src.core.logs import logger
from src.core.security import oauth2_scheme
from src.modules.users.models import User

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
            logger.warning("JWT Token payload is missing 'sub' (email) claim")
            raise credentials_exception
    except jwt.PyJWTError as e:
        logger.warning("Failed to decode JWT token: {error}", error=str(e))
        raise credentials_exception

    query = select(User).where(User.email == email).options(joinedload(User.doctor))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(
            "Token contains email {email}, but user was not found in DB", email=email
        )
        raise credentials_exception

    return user


async def get_current_doctor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.DOCTOR or current_user.doctor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor privileges required",
        )
    return current_user.doctor


async def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN:
        logger.warning(
            "Access denied for user {email} (id={user_id}, role={role}). Admin privileges required.",
            email=current_user.email,
            user_id=current_user.id,
            role=current_user.role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have enough permissions. Admin only!",
        )
    return current_user
