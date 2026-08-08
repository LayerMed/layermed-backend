import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_session
from src.core.enums import UserRole
from src.core.logs import logger

from modules.users.service import get_user_by_id, get_users_by_filters
from modules.users.shemas import UserRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/",
    response_model=list[UserRead],
    summary="Get all users",
    description="Get all users (no doctors) from databse",
)
@cache(expire=3600)
async def get_users(
    name: str | None = None,
    age: int | None = None,
    email: str | None = None,
    role: UserRole | None = None,
    created_at: datetime.datetime | None = None,
    updated_at: datetime.datetime | None = None,
    db: AsyncSession = Depends(get_session),
):
    users = await get_users_by_filters(
        db, name, age, email, role, created_at, updated_at
    )
    return users


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get user from id",
    description="Get one user (no doctors) from databse via id",
)
@cache(expire=600)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_session),
):
    user = await get_user_by_id(user_id, db)
    if user is None:
        logger.warning(
            "Failed to fetch user: User with id {user_id} not found or is a doctor",
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user
