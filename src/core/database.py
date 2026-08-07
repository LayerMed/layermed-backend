import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from src.core.config import settings


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)


class Timestamp:
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    created_at: Mapped[datetime.datetime] = mapped_column(onupdate=func.now(), server_default=func.now())


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