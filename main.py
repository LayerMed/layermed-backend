
from contextlib import asynccontextmanager

from src.core.redis import redis_client
from fastapi import FastAPI
import uvicorn

from src.modules.users.router import router as users_router
from src.modules.symptoms.router import router as symptom_router
from src.modules.cities.router import router as city_router
from src.modules.specialties.router import router as specialty_router
from src.modules.doctors.router import router as doctor_router

import src.core


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await redis_client.aclose()


app = FastAPI(lifespan=lifespan)


app.include_router(users_router)
app.include_router(symptom_router)
app.include_router(city_router)
app.include_router(specialty_router)
app.include_router(doctor_router)


if __name__ == '__main__':
    uvicorn.run('main:app', host="0.0.0.0", port=8000, reload=True)