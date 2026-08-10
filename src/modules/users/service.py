import datetime

from pydantic import EmailStr
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import UserRole
from src.core.logs import logger
from src.core.security import hash_pwd, verify_pwd
from src.modules.users.models import User
from src.modules.users.schemas import (
    PasswordConfirm,
    RegisterUser,
    UserPasswordChange,
    UserUpdate,
)


async def get_users_by_filters(
    db: AsyncSession,
    name: str | None = None,
    birth_date: datetime.date | None = None,
    email: EmailStr | None = None,
    role: UserRole | None = None,
    created_at: datetime.datetime | None = None,
    updated_at: datetime.datetime | None = None,
) -> list[User]:
    logger.info(
        "Start search users with params: {name}, {birth_date}, {email}, {role}, {created_at}, {updated_at}",
        name=name,
        birth_date=birth_date,
        email=email,
        role=role,
        created_at=created_at,
        updated_at=updated_at,
    )
    query = select(User).filter(User.role != UserRole.DOCTOR)
    if name:
        query = query.filter(User.name.ilike(f"%{name}%"))
    if birth_date:
        query = query.filter(User.birth_date == birth_date)
    if email:
        query = query.filter(User.email == email)
    if role:
        query = query.filter(User.role == role)
    if created_at:
        query = query.filter(User.created_at >= created_at)
    if updated_at:
        query = query.filter(User.updated_at >= updated_at)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_user_by_id(user_id: int, db: AsyncSession) -> User | None:
    logger.debug(
        "Executing DB query to fetch user {user_id} (excluding doctors)",
        user_id=user_id,
    )
    query = select(User).filter(User.id == user_id, User.role != UserRole.DOCTOR)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_email(username: EmailStr, db: AsyncSession) -> User | None:
    query = select(User).filter(User.email == username)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_user(new_user: RegisterUser, db: AsyncSession) -> int | None:
    query = (
        insert(User)
        .values(
            name=new_user.name,
            birth_date=new_user.birth_date,
            email=new_user.email,
            password=hash_pwd(new_user.password),
        )
        .on_conflict_do_nothing(index_elements=["email"])
        .returning(User.id)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def update_user(
    user_data: UserUpdate,
    current_user: User,
    db: AsyncSession,
) -> User:
    update_data = user_data.model_dump(exclude_unset=True)
    if not update_data:
        return current_user

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.flush()
    return current_user


async def service_update_password(
    password_data: UserPasswordChange,
    current_user: User,
    db: AsyncSession,
) -> bool:
    if not verify_pwd(password_data.old_password, current_user.password):
        return False

    hashed_password = hash_pwd(password_data.new_password)
    query = (
        update(User)
        .where(User.id == current_user.id)
        .values(password=hashed_password)
    )
    await db.execute(query)
    return True


async def service_delete_account(
    password_data: PasswordConfirm,
    current_user: User,
    db: AsyncSession,
) -> bool:
    if not verify_pwd(password_data.password, current_user.password):
        return False

    query = delete(User).where(User.id == current_user.id)
    await db.execute(query)
    return True