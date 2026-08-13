import redis.asyncio as aioredis

from src.core.config import settings


redis_client = aioredis.from_url(
    settings.redis_dsn, encoding="utf-8", decode_responses=True
)


async def get_redis() -> aioredis.Redis:
    return redis_client
