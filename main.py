from contextlib import asynccontextmanager

import jwt
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

from src.api import api_router
from src.common.exceptions import AppError
from src.core.config import settings
from src.core.limiter import limiter
from src.core.logs import logger
from src.services.storage.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await redis_client.aclose()


app = FastAPI(lifespan=lifespan)


app.include_router(api_router)


@app.exception_handler(AppError)
async def app_error_handle(request: Request, exc: AppError):
    logger.warning("App error occurred on {}: {}", request.url.path, exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handle(request: Request, exc: RequestValidationError):
    logger.warning("Request validation failed on {}: {}", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(HTTPException)
async def http_error_handle(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": jsonable_encoder(exc.detail)},
        headers=exc.headers,
    )


@app.exception_handler(jwt.PyJWTError)
async def jwt_error_handle(request: Request, exc: jwt.PyJWTError):
    logger.warning("JWT validation failed on {}: {}", request.url.path, str(exc))
    return JSONResponse(
        status_code=401,
        content={"detail": "Could not validate credentials or token expired"},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handle(request: Request, exc: SQLAlchemyError):
    db_session = getattr(request.state, "db", None)
    if db_session is not None:
        try:
            await db_session.rollback()
        except Exception:
            pass
    logger.exception("SQLAlchemy error on {}", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error"},
    )


@app.exception_handler(Exception)
async def unhandled_error_handle(request: Request, exc: Exception):
    logger.exception("Unhandled error on {}", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
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
