from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel, ConfigDict

from src.common.enums import ModerationStatus
from src.modules.doctors.models import Doctor
from src.services.moderation.exceptions import ItemNotFoundError
from src.services.moderation.service import update_moderation_status


class ModeratedItemRead(BaseModel):
    id: int
    status: ModerationStatus
    rejection_reason: str | None

    model_config = ConfigDict(from_attributes=True)


async def test_update_moderation_status_commits_and_invalidates_all_namespaces():
    updated = SimpleNamespace(
        id=7,
        status=ModerationStatus.REJECTED,
        rejection_reason="Incomplete profile",
    )
    result = Mock()
    result.scalar_one_or_none.return_value = updated
    db = AsyncMock()
    db.execute.return_value = result
    redis = AsyncMock()

    item = await update_moderation_status(
        model=Doctor,
        schema=ModeratedItemRead,
        item_id=7,
        status=ModerationStatus.REJECTED,
        rejection_reason="Incomplete profile",
        db=db,
        redis=redis,
        cache_namespaces=["doctors", "users"],
    )

    assert item == ModeratedItemRead.model_validate(updated)
    assert [call.args[0] for call in redis.invalidate.await_args_list] == [
        "doctors",
        "users",
    ]
    db.commit.assert_awaited_once()


async def test_update_moderation_status_not_found_does_not_commit_or_invalidate():
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute.return_value = result
    redis = AsyncMock()

    with pytest.raises(ItemNotFoundError, match="Doctor not found"):
        await update_moderation_status(
            model=Doctor,
            schema=ModeratedItemRead,
            item_id=999,
            status=ModerationStatus.APPROVED,
            db=db,
            redis=redis,
            cache_namespaces="doctors",
        )

    db.commit.assert_not_awaited()
    redis.invalidate.assert_not_awaited()
