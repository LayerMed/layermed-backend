from datetime import timedelta
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_DB: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    # PostgreSQL for tests
    TEST_POSTGRES_USER: str
    TEST_POSTGRES_DB: str
    TEST_POSTGRES_PASSWORD: str
    TEST_POSTGRES_PORT: int

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: int
    REDIS_DB: int = 0

    # S3
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_NAME: str

    # JWT Settings
    KEY: str
    ALGORITHM: Literal["HS256"]
    ACCESS_TOKEN_EXPIRE: int = 15 * 60
    REFRESH_TOKEN_EXPIRE: int = 30 * 24 * 60 * 60

    DUMMY_HASH: str
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def pg_psycopg_dsn(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def pg_asyncpg_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def pg_test_asyncpg_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.TEST_POSTGRES_USER}:{self.TEST_POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.TEST_POSTGRES_PORT}/{self.TEST_POSTGRES_DB}"

    @property
    def redis_dsn(self):
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
