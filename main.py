from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from src.core.logs import logger
from src.core.exceptions import AppError
from src.core.redis import redis_client
from src.modules.users.router import router as users_router
from src.modules.symptoms.router import router as symptom_router
from src.modules.cities.router import router as city_router
from src.modules.specialties.router import router as specialty_router
from src.modules.doctors.router import router as doctor_router
from src.modules.bookings.router import router as booking_router

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
app.include_router(booking_router)


@app.exception_handler(AppError)
async def app_error_handle(request: Request, exc: AppError):
    logger.warning(f"App error occurred on {request.url.path}: {exc.detail}")

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
