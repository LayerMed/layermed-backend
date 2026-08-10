import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.enums import UserRole
from src.core.logs import logger
from src.core.security import create_access_token, verify_pwd
from src.modules.users.schemas import RegisterUser, UserLogin, UserRead
from src.modules.users.service import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_users_by_filters,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/",
    response_model=list[UserRead],
    summary="Get all users",
    description="Get all users (no doctors) from databse",
)
async def get_users(
    name: str | None = None,
    birth_date: datetime.date | None = None,
    email: str | None = None,
    role: UserRole | None = None,
    created_at: datetime.datetime | None = None,
    updated_at: datetime.datetime | None = None,
    db: AsyncSession = Depends(get_session),
):
    users = await get_users_by_filters(
        db, name, birth_date, email, role, created_at, updated_at
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


@router.post("/login")
async def login_user(user_data: UserLogin, db: AsyncSession = Depends(get_session)):
    user = await get_user_by_email(user_data.email, db)
    if user is None:
        logger.info("Such user is not exists")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if not verify_pwd(user_data.password, user.password):
        logger.info("The password doesn't fit")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="The password doesn't fit"
        )
    token = create_access_token({"sub": user_data.email})
    return {"access_token": token, "token_type": "bearer"}


@router.post(
    "/register",
    summary="Registering a new user",
    description="Length: strictly from 8 to 16 characters. Without simple passwords",
)
async def register_user(
    new_user: RegisterUser, db: AsyncSession = Depends(get_session)
):
    user_id = await create_user(new_user, db)
    if user_id is None:
        logger.warning(
            "Failed to register: Email {email} already exists", email=new_user.email
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    token = create_access_token({"sub": new_user.email})
    return {"access_token": token, "token_type": "bearer"}
