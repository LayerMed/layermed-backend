import asyncio
from sqlalchemy import select

from src.services.storage.postgres import async_session_maker
from src.core.security import hash_pwd  
from src.modules.users.models import User, UserRole 

USERS_TO_SEED = [
    {
        "email": "client@demo.com",
        "password": "Demo12345!",
        "role": UserRole.CLIENT,
    },
    {
        "email": "doctor@demo.com",
        "password": "Demo12345!",
        "role": UserRole.DOCTOR,
    },
    {
        "email": "admin@demo.com",
        "password": "Demo12345!",
        "role": UserRole.ADMIN,
    },
]


async def seed_users() -> None:
    async with async_session_maker() as session:
        for user_data in USERS_TO_SEED:
            query = select(User).where(User.email == user_data["email"])
            existing_user = await session.scalar(query)

            if not existing_user:
                new_user = User(
                    email=user_data["email"],
                    hashed_password=hash_pwd(user_data["password"]),
                    role=user_data["role"],
                    is_active=True,
                )
                session.add(new_user)            

        await session.commit()
