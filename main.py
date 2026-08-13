from contextlib import asynccontextmanager
from fastapi_cache import FastAPICache
from fastapi import FastAPI
import uvicorn

from fastapi_cache.backends.redis import RedisBackend
from src.core.redis import redis_client

from src.modules.users.router import router as users_router
from src.modules.symptoms.router import router as symptom_router
from src.modules.cities.router import router as city_router

import src.core

@asynccontextmanager
async def lifespan(app: FastAPI):
    FastAPICache.init(RedisBackend(redis_client), prefix='fastapi-cache')
    yield
    await redis_client.close()

app = FastAPI(lifespan=lifespan)

app.include_router(users_router)
app.include_router(symptom_router)
app.include_router(city_router)

if __name__ == '__main__':
    uvicorn.run('main:app', reload=True)