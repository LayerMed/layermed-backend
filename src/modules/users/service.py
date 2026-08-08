import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.enums import UserRole
from src.core.logs import logger
from src.modules.users.models import User


async def get_users_by_filters(
    db: AsyncSession,
    name: str | None = None,
    age: int | None = None,
    email: str | None = None,
    role: UserRole | None = None,
    created_at: datetime.datetime | None = None,
    updated_at: datetime.datetime | None = None,
) -> list[User]:
    logger.info(
        "Start search users with params: {name}, {age}, {email}, {role}, {created_at}, {updated_at}",
        name=name,
        age=age,
        email=email,
        role=role,
        created_at=created_at,
        updated_at=updated_at,
    )
    query = select(User).filter(User.role != UserRole.DOCTOR)
    if name:
        query = query.filter(User.name.ilike(f"%{name}%"))
    if age:
        query = query.filter(User.age == age)
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
