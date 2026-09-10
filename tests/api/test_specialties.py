import pytest
from sqlalchemy import select

from src.common.enums import CacheTTL
from src.modules.specialties.models import Specialty
from src.modules.specialties.schemas import SpecialtyCreate, SpecialtyRead

name = "otolaryngologist"
description = "An otolaryngologist is a medical specialist who diagnoses and treats conditions related to the ears, nose, and throat"
payload = {
    "name": name,
    "description": description
}


@pytest.fixture
async def created_specialty(ac, fake_get_admin_user):
    response = await ac.post("/specialties/", json=payload)
    assert response.status_code == 201
    return response.json()


class TestCreatespecialty:
    async def test_create_specialty(self, ac, get_test_session, fake_get_admin_user):
        response = await ac.post("/specialties/", json=payload)
        data = response.json()

        assert response.status_code == 201
        assert data["id"] is not None
        assert data["name"] == name
        assert data["description"] == description

        query = select(Specialty).where(Specialty.id == data["id"])
        specialty = await get_test_session.execute(query)
        assert specialty.scalar_one_or_none() is not None

    async def test_create_specialty_validation_error(self, ac, fake_get_admin_user):
        long_payload = {
            "name": "Surgeon",
            "name": "Long" * 100,
        }
        response = await ac.post("/specialties/", json=long_payload)
        assert response.status_code == 422

    async def test_create_specialty_already_exists_error(self, ac, fake_get_admin_user):
        first = await ac.post("/specialties/", json=payload)
        assert first.status_code == 201

        second = await ac.post("/specialties/", json=payload)
        assert second.status_code == 409

    async def test_create_specialty_cache(self, ac, fake_get_redis, fake_get_admin_user):
        cache_key = fake_get_redis.build_key("specialties", "items", "all")

        await fake_get_redis.setc(
            cache_key, SpecialtyCreate.model_validate(payload), CacheTTL.STATIC
        )

        cached_specialties = await fake_get_redis.getc(cache_key)
        assert cached_specialties is not None

        await ac.post("/specialties/", json=payload)
        cached_specialties = await fake_get_redis.getc(cache_key)
        assert cached_specialties is None

    async def test_create_specialty_access(self, ac):
        response = await ac.post("/specialties/", json=payload)
        assert response.status_code == 401


class TestReadspecialty:
    async def test_get_specialties(self, ac, created_specialty, get_test_session):
        response = await ac.get("/specialties/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_specialties_cache(self, ac, fake_get_redis):
        cache_key = fake_get_redis.build_key("specialties", "items", "all")

        cached_specialties = await fake_get_redis.getc(cache_key)
        assert cached_specialties is None

        response = await ac.get("/specialties/")
        assert response.status_code == 200

        cached_specialties = await fake_get_redis.getc(cache_key)
        assert cached_specialties is not None

    async def test_get_specialty_by_id(self, ac, created_specialty):
        response_get = await ac.get(f"/specialties/{created_specialty['id']}")
        assert response_get.status_code == 200

        fetched_specialty = SpecialtyRead.model_validate_json(response_get.text)
        assert fetched_specialty.id == created_specialty["id"]

    async def test_get_specialty_by_id_not_found_error(self, ac):
        response_get = await ac.get("/specialties/9999")
        assert response_get.status_code == 404

    async def test_get_specialty_by_id_cache(self, ac, fake_get_redis, created_specialty):

        cache_key = fake_get_redis.build_key("specialties", "items", "all")

        cached_specialties = await fake_get_redis.getc(cache_key)
        assert cached_specialties is None

        response_get = await ac.get(f"/specialties/{created_specialty['id']}")
        assert response_get.status_code == 200

        cached_specialties = await fake_get_redis.getc(cache_key)
        assert cached_specialties is not None


class TestUpadtespecialty:
    async def test_update_specialty(self, ac, get_test_session, created_specialty):
        update_payload = {"name": "Updated name"}

        response_update = await ac.patch(
            f"/specialties/{created_specialty['id']}", json=update_payload
        )

        assert response_update.status_code == 200
        data_updated = response_update.json()
        assert data_updated["id"] == created_specialty["id"]
        assert data_updated["name"] == update_payload["name"]

        query = select(Specialty).where(Specialty.id == created_specialty["id"])
        result = await get_test_session.execute(query)
        db_specialty = result.scalar_one()

        assert db_specialty.name == update_payload["name"]

    async def test_update_specialty_cache(self, ac, fake_get_redis, created_specialty):
        update_payload = {
            "name": "Updated name",
        }
        cache_key = fake_get_redis.build_key("specialties", "items", "all")

        await fake_get_redis.setc(cache_key, payload, CacheTTL.STATIC)

        cached_specialty = await fake_get_redis.getc(cache_key)
        assert cached_specialty is not None

        await ac.patch(f"/specialties/{created_specialty['id']}", json=update_payload)

        cached_specialty = await fake_get_redis.getc(cache_key)
        assert cached_specialty is None

    async def test_update_specialty_not_found_error(self, ac, fake_get_admin_user):
        response = await ac.patch("/specialties/9999", json=payload)
        assert response.status_code == 404


class TestDeletespecialty:
    async def test_delete_specialty(self, ac, created_specialty):
        response = await ac.delete(f"/specialties/{created_specialty['id']}")
        assert response.status_code == 204

    async def test_delete_specialty_cache(self, ac, fake_get_redis, created_specialty):
        cache_key = fake_get_redis.build_key("specialties", "items", "all")

        await fake_get_redis.setc(cache_key, payload, CacheTTL.STATIC)

        cached_specialty = await fake_get_redis.getc(cache_key)
        assert cached_specialty is not None

        await ac.delete(f"/specialties/{created_specialty['id']}")

        cached_specialty = await fake_get_redis.getc(cache_key)
        assert cached_specialty is None

    async def test_delete_specialty_not_found_error(self, ac, fake_get_admin_user):
        response = await ac.delete("/specialties/9999")
        assert response.status_code == 404
