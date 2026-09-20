import asyncio

from pydantic import EmailStr
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.common.enums import UserRole
from src.common.schemas import PaginatedResponse, PasswordConfirm
from src.core.config import settings
from src.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_pwd,
    verify_pwd,
)
from src.modules.users.exceptions import (
    IncorrectPasswordError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from src.modules.users.models import User
from src.modules.users.schemas import (
    UserCreate,
    UserFilterParams,
    UserPasswordUpdate,
    UserRead,
    UserUpdate,
)
from src.services.storage.redis import RedisCache


# TOKEN
async def tokens_for_user(user: User, redis: RedisCache) -> tuple[str, str]:
    access_token = create_access_token(
        {"sub": user.email},
        user.token_version,
    )
    refresh_token = generate_refresh_token()

    refresh_key = redis.build_key("users", "refresh", refresh_token)
    await redis.setc(refresh_key, user.email, ex=settings.REFRESH_TOKEN_EXPIRE)

    return access_token, refresh_token


async def refresh_user_session(
    refresh_token: str | None,
    db: AsyncSession,
    redis: RedisCache,
) -> tuple[str, str]:
    if not refresh_token:
        raise InvalidCredentialsError(detail="Refresh token missing")

    refresh_key = redis.build_key("users", "refresh", refresh_token)
    email = await redis.getc(refresh_key)

    if not email:
        raise InvalidCredentialsError(detail="Invalid or expired refresh token")

    await redis.delc(refresh_key)

    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise UserNotFoundError()

    return await tokens_for_user(user, redis)


async def revoke_refresh_session(refresh_token: str | None, redis: RedisCache) -> None:
    if refresh_token:
        refresh_key = redis.build_key("users", "refresh", refresh_token)
        await redis.delc(refresh_key)


# CREATE
async def create_user(new_user: UserCreate, db: AsyncSession) -> User:
    query = (
        insert(User)
        .on_conflict_do_nothing()
        .values(
            name=new_user.name,
            city_id=new_user.city_id,
            birth_date=new_user.birth_date,
            email=new_user.email,
            password=hash_pwd(new_user.password),
        )
        .returning(User)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise UserAlreadyExistsError()

    await db.commit()
    return user


# READ
async def get_users_by_filters(
    filters: UserFilterParams,
    db: AsyncSession,
) -> PaginatedResponse[UserRead]:
    query = (
        select(User)
        .filter(User.role != UserRole.ADMIN)
        .options(selectinload(User.doctor))
    )

    if filters.name:
        query = query.filter(User.name.ilike(f"%{filters.name}%"))
    if filters.birth_date:
        query = query.filter(User.birth_date == filters.birth_date)
    if filters.email:
        query = query.filter(User.email == filters.email)
    if filters.city_id:
        query = query.filter(User.city_id == filters.city_id)
    if filters.role:
        query = query.filter(User.role == filters.role)
    if filters.created_at:
        query = query.filter(User.created_at >= filters.created_at)
    if filters.updated_at:
        query = query.filter(User.updated_at >= filters.updated_at)

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.limit(filters.limit).offset(filters.offset)
    result = await db.execute(query)
    users = result.scalars().all()

    return PaginatedResponse[UserRead](
        items=[UserRead.model_validate(u) for u in users],
        limit=filters.limit,
        offset=filters.offset,
        total=total,
    )


async def get_user_by_id(user_id: int, db: AsyncSession) -> UserRead:
    query = select(User).filter(User.id == user_id).options(selectinload(User.doctor))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError()
    return UserRead.model_validate(user)


async def get_user_by_email(username: EmailStr, db: AsyncSession) -> User:
    query = select(User).filter(User.email == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if user is None:
        raise InvalidCredentialsError()
    return user


async def get_user_password(current_user: UserRead, db: AsyncSession) -> str:
    query_password = select(User.password).where(User.id == current_user.id)
    result = await db.execute(query_password)
    current_password = result.scalar_one_or_none()
    if current_password is None:
        raise UserNotFoundError()
    return current_password


# UPDATE
async def update_user(
    user_data: UserUpdate,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> UserRead:
    update_data = user_data.model_dump(exclude_unset=True)
    if not update_data:
        return current_user

    update_query = update(User).where(User.id == current_user.id).values(**update_data)
    await db.execute(update_query)

    select_query = (
        select(User).where(User.id == current_user.id).options(joinedload(User.doctor))
    )
    result = await db.execute(select_query)
    updated_user = result.scalar_one_or_none()

    await db.commit()

    cache_key = redis.build_key("users", "current", current_user.email)
    await redis.delc(cache_key)

    return UserRead.model_validate(updated_user)


async def update_password(
    password_data: UserPasswordUpdate,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> None:
    current_password = await get_user_password(current_user, db)

    if not verify_pwd(password_data.old_password, current_password):
        raise IncorrectPasswordError()

    hashed_password = hash_pwd(password_data.new_password)
    query = (
        update(User)
        .where(User.id == current_user.id)
        .values(password=hashed_password, token_version=User.token_version + 1)
    )

    await db.execute(query)
    await db.commit()

    cache_key = redis.build_key("users", "current", current_user.email)
    await redis.delc(cache_key)


# DELETE
async def delete_account(
    password_data: PasswordConfirm,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> None:
    current_password = await get_user_password(current_user, db)

    if not verify_pwd(password_data.password, current_password):
        raise IncorrectPasswordError()

    query = delete(User).where(User.id == current_user.id)
    await db.execute(query)
    await db.commit()

    tasks = [
        redis.delc(redis.build_key("users", "current", current_user.email)),
        redis.invalidate("users"),
    ]

    if current_user.role == UserRole.DOCTOR:
        tasks.extend(
            [
                redis.invalidate("doctors"),
                redis.invalidate("offers"),
            ]
        )

    await asyncio.gather(*tasks)
