from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.moderation.exceptions import ItemNotFoundError
from src.core.database import Base
from src.core.redis import RedisCache
from src.core.enums import ModerationStatus


ModelT = TypeVar("ModelT", bound=Base)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


async def update_moderation_status(
    model: type[ModelT],
    schema: type[SchemaT],
    item_id: int,
    status: ModerationStatus,
    db: AsyncSession,
    redis: RedisCache,
    cache_namespace: str,
    rejection_reason: str | None = None,
) -> SchemaT:
    query = (
        update(model)
        .where(model.id == item_id)
        .values(status=status, rejection_reason=rejection_reason)
        .returning(model)
    )
    result = await db.execute(query)
    updated_item = result.scalar_one_or_none()

    if updated_item is None:
        raise ItemNotFoundError(detail=f"{model.__name__} not found")

    await db.commit()
    await redis.invalidate(cache_namespace)
    return schema.model_validate(updated_item)


async def approve_item(
    model: type[ModelT],
    schema: type[SchemaT],
    item_id: int,
    db: AsyncSession,
    redis: RedisCache,
    cache_namespace: str,
    rejection_reason: str | None = None,
) -> SchemaT:
    return await update_moderation_status(
        model,
        schema,
        item_id,
        ModerationStatus.APPROVED,
        db,
        redis,
        cache_namespace,
        rejection_reason,
    )


async def reject_item(
    model: type[ModelT],
    schema: type[SchemaT],
    item_id: int,    
    db: AsyncSession,
    redis: RedisCache,
    cache_namespace: str,    
) -> SchemaT:
    return await update_moderation_status(
        model,
        schema,
        item_id,
        ModerationStatus.REJECTED,
        db,
        redis,
        cache_namespace,
        rejection_reason=None
    )

