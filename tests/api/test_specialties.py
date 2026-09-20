import pytest
from sqlalchemy import select

from src.common.enums import CacheTTL
from src.modules.specialties.models import Specialty
from src.modules.specialties.schemas import SpecialtyRead

NAME = "Otolaryngologist"
DESCRIPTION = "Specialist in conditions of the ear, nose, and throat."
PAYLOAD = {"name": NAME, "description": DESCRIPTION}


@pytest.fixture
async def created_specialty(ac, fake_get_admin_user):
    response = await ac.post("/specialties/", json=PAYLOAD)
    assert response.status_code == 201
    return response.json()


class TestCreateSpecialty:
    async def test_create_specialty_success(
        self, ac, get_test_session, fake_get_admin_user
    ):
        response = await ac.post("/specialties/", json=PAYLOAD)
        assert response.status_code == 201
        data = response.json()

        assert data["id"] is not None
        assert data["name"] == NAME
        assert data["description"] == DESCRIPTION

        query = select(Specialty).where(Specialty.id == data["id"])
        result = await get_test_session.execute(query)
        assert result.scalar_one_or_none() is not None

    async def test_create_specialty_validation_error(self, ac, fake_get_admin_user):
        long_payload = {"name": "Long" * 100, "description": DESCRIPTION}
        response = await ac.post("/specialties/", json=long_payload)
        assert response.status_code == 422

    async def test_create_specialty_already_exists_error(self, ac, fake_get_admin_user):
        first = await ac.post("/specialties/", json=PAYLOAD)
        assert first.status_code == 201

        second = await ac.post("/specialties/", json=PAYLOAD)
        assert second.status_code == 409
        assert second.json()["detail"] == "Specialty with such name already exists"

    async def test_create_specialty_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user
    ):
        cache_key = fake_get_redis.build_key("specialties", "items", "all")
        await fake_get_redis.setc(cache_key, [{"fake": "list"}], CacheTTL.STATIC)
        assert await fake_get_redis.getc(cache_key) is not None

        response = await ac.post("/specialties/", json=PAYLOAD)
        assert response.status_code == 201
        assert await fake_get_redis.getc(cache_key) is None

    async def test_create_specialty_unauthorized(self, ac):
        response = await ac.post("/specialties/", json=PAYLOAD)
        assert response.status_code == 401

    async def test_create_specialty_forbidden_for_client(
        self, ac, fake_get_current_user
    ):
        response = await ac.post("/specialties/", json=PAYLOAD)
        assert response.status_code == 403


class TestReadSpecialty:
    async def test_get_specialties_success(self, ac, created_specialty):
        response = await ac.get("/specialties/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(s["id"] == created_specialty["id"] for s in data)

    async def test_get_specialties_cache(self, ac, fake_get_redis):
        cache_key = fake_get_redis.build_key("specialties", "items", "all")
        assert await fake_get_redis.getc(cache_key) is None

        response = await ac.get("/specialties/")
        assert response.status_code == 200

        cached_data = await fake_get_redis.getc(cache_key)
        assert cached_data is not None
        assert isinstance(cached_data, list)

    async def test_get_specialty_by_id_success(self, ac, created_specialty):
        response = await ac.get(f"/specialties/{created_specialty['id']}")
        assert response.status_code == 200

        fetched = SpecialtyRead.model_validate_json(response.text)
        assert fetched.id == created_specialty["id"]
        assert fetched.name == created_specialty["name"]

    async def test_get_specialty_by_id_not_found(self, ac):
        response = await ac.get("/specialties/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Specialty not found"

    async def test_get_specialty_by_id_uses_cache(
        self, ac, fake_get_redis, created_specialty
    ):
        cache_key = fake_get_redis.build_key("specialties", "items", "all")
        cached_spec = {
            "id": 888,
            "name": "Cached Specialty",
            "description": "Cached Description",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        await fake_get_redis.setc(cache_key, [cached_spec], CacheTTL.STATIC)

        response = await ac.get("/specialties/888")
        assert response.status_code == 200
        assert response.json()["name"] == "Cached Specialty"

    async def test_get_specialties_count(
        self, ac, get_test_session, doctor_factory, seed_specialties
    ):
        spec1, spec2 = seed_specialties
        await doctor_factory(specialties=[spec1])
        await doctor_factory(specialties=[spec1, spec2])
        await get_test_session.commit()

        response = await ac.get("/specialties/count")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        counts_map = {item["id"]: item["doctors_count"] for item in data}
        assert counts_map.get(spec1.id) == 2
        assert counts_map.get(spec2.id) == 1

    async def test_get_specialties_count_cache(self, ac, fake_get_redis):
        cache_key = fake_get_redis.build_key("specialties", "items", "count")
        cached_payload = [{"id": 1, "name": "Cached Spec", "doctors_count": 5}]
        await fake_get_redis.setc(cache_key, cached_payload, CacheTTL.STATIC)

        response = await ac.get("/specialties/count")
        assert response.status_code == 200
        assert response.json() == cached_payload


class TestUpdateSpecialty:
    async def test_update_specialty_success(
        self, ac, get_test_session, fake_get_admin_user, created_specialty
    ):
        update_payload = {
            "name": "Updated Specialty",
            "description": "Updated specialty full description.",
        }
        response = await ac.patch(
            f"/specialties/{created_specialty['id']}", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_specialty["id"]
        assert data["name"] == update_payload["name"]
        assert data["description"] == update_payload["description"]

        query = select(Specialty).where(Specialty.id == created_specialty["id"])
        result = await get_test_session.execute(query)
        db_spec = result.scalar_one()
        assert db_spec.name == update_payload["name"]

    async def test_update_specialty_empty_body(
        self, ac, fake_get_admin_user, created_specialty
    ):
        response = await ac.patch(f"/specialties/{created_specialty['id']}", json={})
        assert response.status_code == 200
        assert response.json()["name"] == created_specialty["name"]

    async def test_update_specialty_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user, created_specialty
    ):
        cache_key = fake_get_redis.build_key("specialties", "items", "all")
        await fake_get_redis.setc(cache_key, [created_specialty], CacheTTL.STATIC)

        response = await ac.patch(
            f"/specialties/{created_specialty['id']}", json={"name": "New Spec Name"}
        )
        assert response.status_code == 200
        assert await fake_get_redis.getc(cache_key) is None

    async def test_update_specialty_not_found(self, ac, fake_get_admin_user):
        response = await ac.patch(
            "/specialties/99999", json={"name": "Ghost Specialty"}
        )
        assert response.status_code == 404

    async def test_update_specialty_unauthorized(self, ac):
        response = await ac.patch("/specialties/1", json={"name": "Unauthorized"})
        assert response.status_code == 401

    async def test_update_specialty_forbidden_for_client(
        self, ac, fake_get_current_user
    ):
        response = await ac.patch("/specialties/1", json={"name": "Forbidden"})
        assert response.status_code == 403


class TestDeleteSpecialty:
    async def test_delete_specialty_success(
        self, ac, get_test_session, fake_get_admin_user, created_specialty
    ):
        response = await ac.delete(f"/specialties/{created_specialty['id']}")
        assert response.status_code == 204

        query = select(Specialty).where(Specialty.id == created_specialty["id"])
        result = await get_test_session.execute(query)
        assert result.scalar_one_or_none() is None

    async def test_delete_specialty_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user, created_specialty
    ):
        cache_key = fake_get_redis.build_key("specialties", "items", "all")
        await fake_get_redis.setc(cache_key, [created_specialty], CacheTTL.STATIC)

        response = await ac.delete(f"/specialties/{created_specialty['id']}")
        assert response.status_code == 204
        assert await fake_get_redis.getc(cache_key) is None

    async def test_delete_specialty_not_found(self, ac, fake_get_admin_user):
        response = await ac.delete("/specialties/99999")
        assert response.status_code == 404

    async def test_delete_specialty_unauthorized(self, ac):
        response = await ac.delete("/specialties/1")
        assert response.status_code == 401

    async def test_delete_specialty_forbidden_for_client(
        self, ac, fake_get_current_user
    ):
        response = await ac.delete("/specialties/1")
        assert response.status_code == 403
