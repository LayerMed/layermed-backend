from pydantic import BaseModel

from src.services.storage.redis import RedisCache


class CachedItem(BaseModel):
    id: int
    name: str


async def test_setc_and_getc_round_trip_pydantic_model(fake_get_redis: RedisCache):
    item = CachedItem(id=1, name="cardiology")

    await fake_get_redis.setc("items:1", item, ex=60)

    assert await fake_get_redis.getc("items:1") == item.model_dump()


async def test_setc_and_getc_round_trip_list_of_models(fake_get_redis: RedisCache):
    items = [CachedItem(id=1, name="one"), CachedItem(id=2, name="two")]

    await fake_get_redis.setc("items:all", items, ex=60)

    assert await fake_get_redis.getc("items:all") == [
        item.model_dump() for item in items
    ]


async def test_getc_returns_plain_string_when_value_is_not_json(
    fake_get_redis: RedisCache,
):
    await fake_get_redis.redis_client.set("plain", "not-json")

    assert await fake_get_redis.getc("plain") == "not-json"


async def test_invalidate_deletes_only_matching_namespace(fake_get_redis: RedisCache):
    await fake_get_redis.redis_client.mset(
        {"doctors:1": "one", "doctors:2": "two", "offers:1": "other"}
    )

    await fake_get_redis.invalidate("doctors")

    assert await fake_get_redis.getc("doctors:1") is None
    assert await fake_get_redis.getc("doctors:2") is None
    assert await fake_get_redis.getc("offers:1") == "other"
