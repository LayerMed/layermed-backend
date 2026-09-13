from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Callable

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload
from sqlalchemy.pool import NullPool

from main import app
from src.common.enums import ModerationStatus, UserRole
from src.core.config import settings
from src.core.dependencies import (
    get_admin_user,
    get_current_doctor,
    get_current_user,
    get_optional_user,
)
from src.core.security import hash_pwd
from src.modules.cities.models import City
from src.modules.doctors.models import Doctor
from src.modules.doctors.schemas import DoctorRead
from src.modules.users.models import User
from src.modules.users.schemas import UserRead
from src.services.storage.postgres import Base, get_session
from src.services.storage.redis import RedisCache, get_redis

test_engine = create_async_engine(
    settings.pg_test_asyncpg_dsn,
    poolclass=NullPool,
)

test_session_maker = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest.fixture(autouse=True)
async def clean_database():
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE;')
            )


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def ac(get_test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def fake_get_session():
        yield get_test_session

    app.dependency_overrides[get_session] = fake_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.pop(get_session, None)


@pytest.fixture(autouse=True)
async def fake_get_redis() -> AsyncGenerator[RedisCache, None]:
    fake_client = fakeredis.FakeAsyncRedis(decode_responses=True)
    cache = RedisCache(redis_client=fake_client)

    app.dependency_overrides[get_redis] = lambda: cache
    yield cache

    await fake_client.flushdb()
    app.dependency_overrides.pop(get_redis, None)


# =====================================================================
# ФАБРИКИ (FACTORIES) ДЛЯ СОЗДАНИЯ ДАННЫХ
# =====================================================================
@pytest.fixture
def create_user_factory(get_test_session: AsyncSession) -> Callable:
    async def _create_user(
        name: str = "TestUser",
        email: str = "user@test.com",
        role: UserRole = UserRole.CLIENT,
    ) -> User:
        now = datetime.now(UTC).replace(tzinfo=None)
        user = User(
            name=name,
            email=email,
            password=hash_pwd("test_hashed_password"),
            role=role,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(user)
        await get_test_session.commit()
        await get_test_session.refresh(user)
        return user
    return _create_user


@pytest.fixture
def create_doctor_factory(get_test_session: AsyncSession, create_user_factory: Callable) -> Callable:
    async def _create_doctor(
        email: str = "doctor@test.com",
        status: ModerationStatus = ModerationStatus.APPROVED,
    ) -> Doctor:
        now = datetime.now(UTC).replace(tzinfo=None)
        user = await create_user_factory(name="TestDoctor", email=email, role=UserRole.DOCTOR)
        
        doctor = Doctor(
            user_id=user.id,
            education="Harvard Medical School",
            degree="MD",
            experience_years=10,
            bio="Board-certified specialist.",
            min_price=150,
            clinic="Main Clinic",
            rating_avg=5.0,
            reviews_count=10,
            status=status,
            rejection_reason=None,
            created_at=now,
            updated_at=now,
        )
        get_test_session.add(doctor)
        await get_test_session.commit()
        
        stmt = select(User).where(User.id == user.id).options(joinedload(User.doctor))
        res = await get_test_session.execute(stmt)
        full_user = res.scalar_one()
        return full_user.doctor
    return _create_doctor


# =====================================================================
# ПЕРЕОПРЕДЕЛЕНИЯ ЗАВИСИМОСТЕЙ (DEPENDENCY OVERRIDES)
# =====================================================================
@pytest.fixture
def fake_admin_user() -> UserRead:
    now = datetime.now(UTC).replace(tzinfo=None)
    return UserRead(
        id=1,
        name="TestAdmin",
        email="admin@test.com",
        role=UserRole.ADMIN,
        updated_at=now,
        created_at=now,
    )


@pytest.fixture
def fake_get_admin_user(fake_admin_user: UserRead):
    app.dependency_overrides[get_admin_user] = lambda: fake_admin_user
    yield fake_admin_user
    app.dependency_overrides.pop(get_admin_user, None)


@pytest.fixture
def fake_optional_admin_user(fake_admin_user: UserRead):
    app.dependency_overrides[get_optional_user] = lambda: fake_admin_user
    yield fake_admin_user
    app.dependency_overrides.pop(get_optional_user, None)


@pytest.fixture
async def fake_get_current_user(create_user_factory: Callable) -> AsyncGenerator[UserRead, None]:
    user = await create_user_factory()
    user_read = UserRead.model_validate(user)
    
    app.dependency_overrides[get_current_user] = lambda: user_read
    yield user_read
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def fake_get_current_user_as_doctor(create_doctor_factory: Callable) -> AsyncGenerator[UserRead, None]:
    doctor = await create_doctor_factory()
    user_read = UserRead.model_validate(doctor.user)

    app.dependency_overrides[get_current_user] = lambda: user_read
    yield user_read
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def fake_get_current_doctor(create_doctor_factory: Callable) -> AsyncGenerator[DoctorRead, None]:
    doctor = await create_doctor_factory(email="current_doc@test.com")
    doctor_read = DoctorRead.model_validate(doctor)

    app.dependency_overrides[get_current_doctor] = lambda: doctor_read
    yield doctor_read
    app.dependency_overrides.pop(get_current_doctor, None)