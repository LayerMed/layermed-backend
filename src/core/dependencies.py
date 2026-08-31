import jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.core.config import settings
from src.core.database import get_session
from src.core.enums import CacheTTL, UserRole
from src.core.logs import logger
from src.core.redis import RedisCache, get_redis
from src.core.security import oauth2_scheme
from src.modules.doctors.schemas import DoctorRead
from src.modules.users.models import User
from src.modules.users.schemas import UserRead


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials or token expired",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> UserRead:
    try:
        payload = jwt.decode(token, settings.KEY, algorithms=settings.ALGORITHM)
        email = payload.get("sub")
        if email is None:
            logger.warning("JWT Token payload is missing 'sub' (email) claim")
            raise credentials_exception
    except jwt.PyJWTError as e:
        logger.warning("Failed to decode JWT token: {error}", error=str(e))
        raise credentials_exception

    cache_key = redis.build_key("users", "current", email)
    cached_user = await redis.getc(cache_key)
    if cached_user is not None:
        try:
            return UserRead.model_validate(cached_user)
        except Exception:
            logger.info(
                "Outdated cache structure for user {email}. Refreshing from database.",
                email=email,
            )
            await redis.delc(cache_key)

    query = select(User).where(User.email == email).options(joinedload(User.doctor))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(
            "Token contains email {email}, but user was not found in DB", email=email
        )
        raise credentials_exception

    user_dto = UserRead.model_validate(user)
    await redis.setc(cache_key, user_dto, ex=CacheTTL.FAST)
    return user_dto


async def get_current_doctor(
    current_user: UserRead = Depends(get_current_user),
) -> DoctorRead:
    if current_user.role != UserRole.DOCTOR or current_user.doctor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor privileges required",
        )
    return current_user.doctor


async def get_admin_user(current_user: UserRead = Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN:
        logger.warning(
            "Access denied for user {email} (id={user_id}, role={role}). Admin privileges required.",
            email=current_user.email,
            user_id=current_user.id,
            role=current_user.role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have enough permissions",
        )
    return current_user
