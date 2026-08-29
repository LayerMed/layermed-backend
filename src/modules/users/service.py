from pydantic import EmailStr
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.core.enums import UserRole
from src.core.redis import RedisCache
from src.core.schemas import PaginatedResponse, PasswordConfirm
from src.core.security import hash_pwd, verify_pwd
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


async def get_user_password(current_user: UserRead, db: AsyncSession) -> str:
    query_password = select(User.password).where(User.id == current_user.id)
    result  = await db.execute(query_password)
    current_password = result.scalar_one_or_none()
    if current_password is None:
        raise UserNotFoundError()
    return current_password


# CREATE
async def create_user(new_user: UserCreate, db: AsyncSession) -> int | None:
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
        .returning(User.id)
    )
    result = await db.execute(query)
    user_id = result.scalar_one_or_none()

    if user_id is None:
        raise UserAlreadyExistsError()

    return user_id


# READ
async def get_users_by_filters(
    filters: UserFilterParams,
    db: AsyncSession,
) -> PaginatedResponse[UserRead]:
    query = (
        select(User)
        .filter(User.role != UserRole.ADMIN)
        .options(selectinload(User.doctor))
        .limit(filters.limit)
        .offset(filters.offset)
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

    query = query.limit(filters.limit).offset(filters.offset)
    result = await db.execute(query)
    users = result.scalars().all()

    return PaginatedResponse[UserRead](
        items=[UserRead.model_validate(u) for u in users],
        limit=filters.limit,
        offset=filters.offset,
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
    updated_user = result.scalar_one()

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
        update(User).where(User.id == current_user.id).values(password=hashed_password)
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

    cache_key = redis.build_key("users", "current", current_user.email)
    await redis.delc(cache_key)
