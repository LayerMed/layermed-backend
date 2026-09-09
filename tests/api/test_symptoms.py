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

name = "Runny nose"
description = (
    "A runny nose is a condition where the nasal passages produce excess mucus."
)
payload = {
    "name": name,
    "description": description,
}


class TestCreateSymptom:
    async def test_create_symptom_success(
        self, ac, get_test_session, fake_get_admin_user
    ):
        response = await ac.post("/symptoms/", json=payload)
        data = response.json()

        assert response.status_code == 201
        assert data["id"] is not None
        assert data["name"] == name
        assert data["description"] == description

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
        first = await ac.post("/symptoms/", json=payload)
        assert first.status_code == 201

        second = await ac.post("/symptoms/", json=payload)
        assert second.status_code == 409

    async def test_create_symptom_cache(self, ac, fake_get_redis, fake_get_admin_user):
        cache_key = fake_get_redis.build_key("symptoms", "items", "all")

        await fake_get_redis.setc(
            cache_key, SymptomCreate.model_validate(payload), CacheTTL.STATIC
        )

        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is not None

        await ac.post("/symptoms/", json=payload)
        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is None

    async def test_create_symptom_access(self, ac):
        response = await ac.post("/symptoms/", json=payload)
        assert response.status_code == 401


class TestReadSymptom:
    async def test_get_symptoms(self, ac, get_test_session):
        symptom = Symptom(
            name="Cough",
            description="A cough is a reflex action that helps clear the throat and airways of mucus, irritants, or foreign particles.",
        )
        get_test_session.add(symptom)
        await get_test_session.commit()

        response = await ac.get("/symptoms/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_symptoms_cache(self, ac, fake_get_redis):
        cache_key = fake_get_redis.build_key("symptoms", "items", "all")

        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is None

        response = await ac.get("/symptoms/")
        assert response.status_code == 200

        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is not None

    async def test_get_symptom_by_id(self, ac, get_test_session, fake_get_admin_user):
        response_create = await ac.post("/symptoms/", json=payload)
        assert response_create.status_code == 201

        created_symptom = SymptomRead.model_validate_json(response_create.text)
        response_get = await ac.get(f"/symptoms/{created_symptom.id}")

        assert response_get.status_code == 200        

        fetched_symptom = SymptomRead.model_validate_json(response_get.text)
        assert fetched_symptom.id == created_symptom.id

    async def test_get_symptom_by_id_not_found_error(self, ac):
        response_get = await ac.get("/symptoms/9999")
        assert response_get.status_code == 404

    async def test_get_symptom_by_id_cache(
        self, ac, fake_get_redis, fake_get_admin_user
    ):
        response_create = await ac.post("/symptoms/", json=payload)
        assert response_create.status_code == 201
        created_symptom = SymptomRead.model_validate_json(response_create.text)        

        cache_key = fake_get_redis.build_key("symptoms", "items", "all")

        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is None

        response_get = await ac.get(f"/symptoms/{created_symptom.id}")
        assert response_get.status_code == 200

        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is not None


        