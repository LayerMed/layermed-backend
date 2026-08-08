from contextlib import asynccontextmanager
from fastapi_cache import FastAPICache
from fastapi import FastAPI
import uvicorn
from src.modules.users import router
from fastapi_cache.backends.redis import RedisBackend
from src.core.redis import redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    FastAPICache.init(RedisBackend(redis_client), prefix='fastapi-cache')
    yield
    await redis_client.aclose()

app = FastAPI()
app.include_router(
    router
)

if __name__ == '__main__':
    uvicorn.run('main.py:app', reload=True)