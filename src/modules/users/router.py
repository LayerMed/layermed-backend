from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_admin_user, get_current_user
from src.core.redis import RedisCache, get_redis
from src.core.schemas import PasswordConfirm, TokenResponse
from src.core.security import create_access_token, verify_pwd
from src.modules.users.exceptions import InvalidCredentialsError
from src.modules.users.models import User
from src.modules.users.schemas import (
    UserCreate,
    UserFilterParams,
    UserPasswordUpdate,
    UserRead,
    UserUpdate,
)
from src.modules.users.service import (
    create_user,
    delete_account,
    get_user_by_email,
    get_user_by_id,
    get_users_by_filters,
    update_password,
    update_user,
)

router = APIRouter(prefix="/users", tags=["Users"])


# CREATE
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registering a new user",
)
async def register_user_handle(
    new_user: UserCreate,
    db: AsyncSession = Depends(get_session),
) -> TokenResponse:
    await create_user(new_user, db)
    token = create_access_token({"sub": new_user.email})
    return TokenResponse(access_token=token)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
)
async def login_user_handle(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user = await get_user_by_email(form_data.username, db)
    if not verify_pwd(form_data.password, user.password):
        raise InvalidCredentialsError()

    token = create_access_token({"sub": form_data.username})
    return TokenResponse(access_token=token)


# READ
@router.get(
    "/",
    response_model=list[UserRead],
    summary="Get all users",
)
async def get_users_by_filters_handle(
    user_params: Annotated[UserFilterParams, Depends()],
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> list[UserRead]:
    users = await get_users_by_filters(user_params, db)
    return users


@router.get(
    "/user/{user_id}",
    response_model=UserRead,
    summary="Get user by id",
)
async def get_user_by_id_handle(
    user_id: int,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> UserRead:
    user = await get_user_by_id(user_id, db)
    return user


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current active user",
)
async def get_me_handle(current_user: UserRead = Depends(get_current_user)) -> UserRead:
    return current_user


# UPDATE
@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update basic profile information",
)
async def update_user_basic_handle(
    user_data: UserUpdate,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> UserRead:
    current_user = await update_user(user_data, current_user, db, redis)
    return current_user


@router.patch(
    "/me/password",
    response_model=dict[str, str],
    summary="Change user password",
)
async def update_user_password_handle(
    password_data: UserPasswordUpdate,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> dict[str, str]:
    await update_password(password_data, current_user, db, redis)
    return {"message": "Password successfully updated"}


# DELETE
@router.delete(
    "/me/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete current user account",
)
async def delete_user_account_handle(
    password_data: PasswordConfirm,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> None:
    await delete_account(password_data, current_user, db, redis)
