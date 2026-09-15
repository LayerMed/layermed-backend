from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.common.schemas import PaginatedResponse, PasswordConfirm, TokenResponse
from src.core.dependencies import get_admin_user, get_current_user
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
    refresh_user_session,
    revoke_refresh_session,
    tokens_for_user,
    update_password,
    update_user,
)
from src.services.storage.postgres import get_session
from src.services.storage.redis import RedisCache, get_redis

router = APIRouter(prefix="/users", tags=["Users"])


# TOKEN
def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False, # потом поставить true
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using cookie",
)
async def refresh_tokens_handle(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> TokenResponse:
    new_access_token, new_refresh_token = await refresh_user_session(
        refresh_token, db, redis
    )
    set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=new_access_token)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
)
async def login_user_handle(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> TokenResponse:
    user = await get_user_by_email(form_data.username, db)

    target_hash = user.password if user else settings.DUMMY_HASH

    is_password_valid = verify_pwd(form_data.password, target_hash)
    if not user or not is_password_valid:
        raise InvalidCredentialsError()

    access_token, refresh_token = await tokens_for_user(user, redis)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user and revoke refresh token",
)
async def logout_handle(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    redis: RedisCache = Depends(get_redis),
) -> None:
    await revoke_refresh_session(refresh_token, redis)
    response.delete_cookie("refresh_token")


# CREATE
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registering a new user",
)
async def register_user_handle(
    response: Response,
    new_user: UserCreate,
    db: AsyncSession = Depends(get_session),
    redis: RedisCache = Depends(get_redis),
) -> TokenResponse:
    user = await create_user(new_user, db)
    access_token, refresh_token = await tokens_for_user(user, redis)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


# READ
@router.get(
    "/",
    response_model=PaginatedResponse[UserRead],
    summary="Get all users",
)
async def get_users_by_filters_handle(
    user_params: Annotated[UserFilterParams, Depends()],
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> PaginatedResponse[UserRead]:
    users = await get_users_by_filters(user_params, db)
    return users


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current active user",
)
async def get_me_handle(current_user: UserRead = Depends(get_current_user)) -> UserRead:
    return current_user


@router.get(
    "/{user_id}",
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
    "/me",
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
