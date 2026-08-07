
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from src.core.config import settings


class Base(DeclarativeBase):
    pass


psycopg_engine = create_engine(
    settings.pg_psycopg_dsn, 
)

engine = create_async_engine(
    settings.pg_asyncpg_dsn,
    echo=True
)

async_session_maker = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_session():
    async with async_session_maker() as session:
        yield session