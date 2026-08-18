from pydantic import EmailStr
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.dependencies import get_user_password
from src.core.enums import UserRole
from src.core.redis import RedisCache
from src.core.schemas import PasswordConfirm
from src.core.security import hash_pwd, verify_pwd
from src.modules.users.models import User
from src.modules.users.schemas import (
    UserCreate,
    UserFilterParams,
    UserPasswordUpdate,
    UserRead,
    UserUpdate,
)


# CREATE
async def create_user(new_user: UserCreate, db: AsyncSession) -> int | None:
    query = (
        insert(User)
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

    if user_id is not None:
        await db.commit()

    return user_id


# READ
async def get_users_by_filters(
    filters: UserFilterParams,
    db: AsyncSession,
) -> list[User]:
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

    result = await db.execute(query)
    users = list(result.scalars().all())
    return users


async def get_user_by_id(user_id: int, db: AsyncSession) -> User | None:
    query = select(User).filter(User.id == user_id).options(selectinload(User.doctor))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_email(username: EmailStr, db: AsyncSession) -> User | None:
    query = select(User).filter(User.email == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
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
    query = (
        update(User)
        .where(User.id == current_user.id)
        .values(**update_data)
        .returning(User)
    )
    result = await db.execute(query)
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
) -> bool:
    current_password = await get_user_password(current_user, db)
    if current_password is None:
        return False

    if not verify_pwd(password_data.old_password, current_password):
        return False

    hashed_password = hash_pwd(password_data.new_password)
    query = (
        update(User).where(User.id == current_user.id).values(password=hashed_password)
    )
    await db.execute(query)
    await db.commit()
    cache_key = redis.build_key("users", "current", current_user.email)
    await redis.delc(cache_key)
    return True


# DELETE
async def delete_account(
    password_data: PasswordConfirm,
    current_user: UserRead,
    db: AsyncSession,
    redis: RedisCache,
) -> bool:
    current_password = await get_user_password(current_user, db)
    if current_password is None:
        return False

    if not verify_pwd(password_data.password, current_password):
        return False

    query = delete(User).where(User.id == current_user.id)
    await db.execute(query)
    await db.commit()

    cache_key = redis.build_key("users", "current", current_user.email)
    await redis.delc(cache_key)
    
    return True
