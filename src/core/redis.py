import json

import redis.asyncio as aioredis
from pydantic import BaseModel

from src.core.config import settings

redis_client = aioredis.from_url(
    settings.redis_dsn, encoding="utf-8", decode_responses=True
)


type Value = str | int | dict | list | BaseModel


class RedisCache:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis_client = redis_client

    def build_key(self, prefix: str, entity: str, id: int | str):
        return f"{prefix}:{entity}:{id}"

    async def invalidate(self, prefix: str) -> None:
        keys = [key async for key in self.redis_client.scan_iter(match=f"{prefix}*")]
        if keys:
            await self.redis_client.delete(*keys)

    async def setc(self, key: str, value: Value, ex: int):
        if isinstance(value, BaseModel):
            value = value.model_dump_json()
        elif isinstance(value, (dict, list)):
            value = json.dumps(value)
        else:
            value = str(value)
        await self.redis_client.set(key, value, ex)

    async def getc(self, key: str):
        data = await self.redis_client.get(key)
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data

    async def delc(self, key: str) -> None:
        await self.redis_client.delete(key)


async def get_redis() -> RedisCache:
    return RedisCache(redis_client)
