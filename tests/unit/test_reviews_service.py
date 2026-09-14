from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.modules.reviews.service import recalculate_doctor_rating


def result_with_doctor(rating_avg: float, reviews_count: int) -> Mock:
    result = Mock()
    result.scalar_one.return_value = SimpleNamespace(
        rating_avg=rating_avg,
        reviews_count=reviews_count,
    )
    return result


def update_parameters(db: AsyncMock) -> dict:
    statement = db.execute.await_args_list[1].args[0]
    return statement.compile().params


async def test_recalculate_doctor_rating_adds_review_using_weighted_average():
    db = AsyncMock()
    db.execute.side_effect = [result_with_doctor(4.0, 2), Mock()]

    await recalculate_doctor_rating(
        doctor_id=7,
        rating_change=5,
        is_addition=True,
        db=db,
    )

    params = update_parameters(db)
    assert params["rating_avg"] == pytest.approx(13 / 3)
    assert params["reviews_count"] == 3


async def test_recalculate_doctor_rating_removes_review_using_weighted_average():
    db = AsyncMock()
    db.execute.side_effect = [result_with_doctor(4.0, 3), Mock()]

    await recalculate_doctor_rating(
        doctor_id=7,
        rating_change=5,
        is_addition=False,
        db=db,
    )

    params = update_parameters(db)
    assert params["rating_avg"] == pytest.approx(3.5)
    assert params["reviews_count"] == 2


async def test_recalculate_doctor_rating_resets_values_after_last_review_removed():
    db = AsyncMock()
    db.execute.side_effect = [result_with_doctor(5.0, 1), Mock()]

    await recalculate_doctor_rating(
        doctor_id=7,
        rating_change=5,
        is_addition=False,
        db=db,
    )

    params = update_parameters(db)
    assert params["rating_avg"] == 0.0
    assert params["reviews_count"] == 0
