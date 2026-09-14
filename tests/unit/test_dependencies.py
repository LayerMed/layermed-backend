from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from fastapi import HTTPException

from src.common.enums import UserRole
from src.core import dependencies
from src.core.config import settings
from src.modules.users.schemas import UserRead


def make_user(role: UserRole = UserRole.CLIENT) -> UserRead:
    now = datetime.now(UTC)
    return UserRead(
        id=1,
        name="Test User",
        email="user@test.com",
        role=role,
        created_at=now,
        updated_at=now,
    )


async def test_get_current_user_returns_valid_cached_user_without_database_call():
    user = make_user()
    token = jwt.encode({"sub": user.email}, settings.KEY, algorithm=settings.ALGORITHM)
    redis = AsyncMock()
    redis.build_key = Mock(return_value="users:current:user@test.com")
    redis.getc.return_value = user.model_dump(mode="json")
    db = AsyncMock()

    result = await dependencies.get_current_user(token=token, db=db, redis=redis)

    assert result == user
    db.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        jwt.encode({"role": "client"}, settings.KEY, algorithm=settings.ALGORITHM),
    ],
)
async def test_get_current_user_rejects_invalid_or_subjectless_token(token: str):
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_current_user(
            token=token,
            db=AsyncMock(),
            redis=AsyncMock(),
        )

    assert exc_info.value.status_code == 401


async def test_get_admin_user_rejects_non_admin():
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_admin_user(make_user(UserRole.CLIENT))

    assert exc_info.value.status_code == 403


async def test_get_optional_user_swallows_invalid_credentials():
    result = await dependencies.get_optional_user(
        token="invalid",
        db=AsyncMock(),
        redis=AsyncMock(),
    )

    assert result is None


async def test_get_optional_user_without_token_does_not_touch_dependencies():
    db = AsyncMock()
    redis = AsyncMock()

    assert await dependencies.get_optional_user(token=None, db=db, redis=redis) is None
    db.execute.assert_not_awaited()
    redis.getc.assert_not_awaited()
