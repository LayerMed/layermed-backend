from src.modules.symptoms.schemas import SymptomRead, SymptomCreate
from src.modules.symptoms.models import Symptom
from src.modules.symptoms.exceptions import (
    SymptomAlreadyExistsError,
    SymptomNotFoundError,
)
from src.common.enums import CacheTTL

from sqlalchemy import select
import pytest
from pydantic import ValidationError


class TestCreateSymptom:
    name = "Runny nose"
    description = (
        "A runny nose is a condition where the nasal passages produce excess mucus."
    )
    payload = {
        "name": name,
        "description": description,
    }

    async def test_create_symptom_success(
        self, ac, get_test_session, fake_get_admin_user
    ):
        response = await ac.post("/symptoms/", json=self.payload)
        data = response.json()

        assert response.status_code == 201
        assert data["id"] != None
        assert data["name"] == self.name
        assert data["description"] == self.description

        query = select(Symptom).where(Symptom.id == data["id"])
        symptom = await get_test_session.execute(query)
        assert symptom.scalar_one_or_none() is not None

    async def test_create_symptom_validation_error(self, ac, fake_get_admin_user):
        payload = {
            "name": "Runny nose",
            "description": "This text contains more than 100 characters to fully satisfy your request. Writing a short paragraph in English makes it easy to quickly reach and exceed this specific length requirement while keeping the message clear and simple.",
        }
        response = await ac.post("/symptoms/", json=payload)
        assert response.status_code == 422

    async def test_create_symptom_already_exists_error(self, ac, fake_get_admin_user):
        first = await ac.post("/symptoms/", json=self.payload)
        assert first.status_code == 201

        second = await ac.post("/symptoms/", json=self.payload)
        assert second.status_code == 409

    async def test_create_symptom_cache(self, ac, fake_get_redis, fake_get_admin_user):
        cache_key = fake_get_redis.build_key("symptoms", "items", "all")

        await fake_get_redis.setc(
            cache_key, SymptomCreate.model_validate(self.payload), CacheTTL.STATIC
        )

        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is not None

        await ac.post("/symptoms/", json=self.payload)
        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is None

    async def test_create_symptom_access(self, ac):
        response = await ac.post("/symptoms/", json=self.payload)
        assert response.status_code == 401


class TestReadSymptom:
    async def test_get_symptoms(self, ac, fake_get_redis):
        