from datetime import datetime, timezone
from typing import AsyncGenerator
import pytest
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
import fakeredis

from src.core.dependencies import get_current_user
from src.services.storage.redis import RedisCache, get_redis
from src.core.dependencies import get_admin_user
from src.common.enums import UserRole
from src.modules.users.schemas import UserRead
from src.services.storage.postgres import Base, get_session
from src.core.config import settings
from main import app


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
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE;'))


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


@pytest.fixture
def fake_admin_user() -> UserRead:
    now = datetime.now(timezone.utc)
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


@pytest.fixture(autouse=True)
async def fake_get_redis() -> AsyncGenerator[RedisCache, None]:
    fake_client = fakeredis.FakeAsyncRedis(decode_responses=True)
    cache = RedisCache(redis_client=fake_client)

    app.dependency_overrides[get_redis] = lambda: cache
    yield cache

    await fake_client.flushdb()
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
def fake_current_user() -> UserRead:
    now = datetime.now(timezone.utc)
    return UserRead(
        id=1,
        name="TestUser",
        email="user@test.com",
        role=UserRole.CLIENT,
        updated_at=now,
        created_at=now,   
    )

@pytest.fixture
def fake_get_current_user(fake_current_user: UserRead):
    app.dependency_overrides[get_current_user] = lambda: fake_current_user
    yield fake_current_user
    app.dependency_overrides.pop(get_current_user, None)
