from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
import uvicorn

from src.core.limiter import limiter
from src.core.config import settings
from src.core.logs import logger
from src.common.exceptions import AppError
from src.services.storage.redis import redis_client
from src.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await redis_client.aclose()


app = FastAPI(lifespan=lifespan)


app.include_router(api_router)


@app.exception_handler(AppError)
async def app_error_handle(request: Request, exc: AppError):
    logger.warning(f"App error occurred on {request.url.path}: {exc.detail}")

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limiter(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please wait before sending new requests"
        },
        headers={"Retry-After": str(exc.detail)},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
