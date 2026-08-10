import datetime

from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import UserRole
from src.core.logs import logger
from src.core.security import hash_pwd
from src.modules.users.models import User
from src.modules.users.schemas import RegisterUser


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
    users = result.scalars().all()
    return users


async def get_user_by_id(
    user_id: int,
    db: AsyncSession,
):
    logger.debug(
        "Executing DB query to fetch user {user_id} (excluding doctors)",
        user_id=user_id,
    )
    query = select(User).filter(User.id == user_id, User.role != UserRole.DOCTOR)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    return user


async def get_user_by_email(username: EmailStr, db: AsyncSession):
    query = select(User).filter(User.email == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    return user


async def create_user(new_user: RegisterUser, db: AsyncSession):
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
    user_id = result.scalar_one_or_none()

    if not user_id:
        return None

    await db.commit()
    return user_id
