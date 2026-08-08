from contextlib import asynccontextmanager
from fastapi_cache import FastAPICache
from fastapi import FastAPI
import uvicorn
from src.modules.users.router import router as users_router
from fastapi_cache.backends.redis import RedisBackend
from src.core.redis import redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    FastAPICache.init(RedisBackend(redis_client), prefix='fastapi-cache')
    yield
    await redis_client.aclose()

app = FastAPI(lifespan=lifespan)
app.include_router(
    users_router
)

if __name__ == '__main__':
    uvicorn.run('main:app', reload=True)