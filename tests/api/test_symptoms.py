import pytest
from sqlalchemy import select

from src.common.enums import CacheTTL
from src.modules.symptoms.models import Symptom
from src.modules.symptoms.schemas import SymptomRead

NAME = "Runny nose"
DESCRIPTION = (
    "A runny nose is a condition where the nasal passages produce excess mucus."
)
PAYLOAD = {
    "name": NAME,
    "description": DESCRIPTION,
}


@pytest.fixture
async def created_symptom(ac, fake_get_admin_user):
    response = await ac.post("/symptoms/", json=PAYLOAD)
    assert response.status_code == 201
    return response.json()


class TestCreateSymptom:
    async def test_create_symptom_success(
        self, ac, get_test_session, fake_get_admin_user
    ):
        response = await ac.post("/symptoms/", json=PAYLOAD)
        assert response.status_code == 201
        data = response.json()

        assert data["id"] is not None
        assert data["name"] == NAME
        assert data["description"] == DESCRIPTION

        query = select(Symptom).where(Symptom.id == data["id"])
        result = await get_test_session.execute(query)
        assert result.scalar_one_or_none() is not None

    async def test_create_symptom_validation_error(self, ac, fake_get_admin_user):
        long_payload = {
            "name": "Runny nose",
            "description": "Long" * 100,
        }
        response = await ac.post("/symptoms/", json=long_payload)
        assert response.status_code == 422

    async def test_create_symptom_already_exists_error(self, ac, fake_get_admin_user):
        first = await ac.post("/symptoms/", json=PAYLOAD)
        assert first.status_code == 201

        second = await ac.post("/symptoms/", json=PAYLOAD)
        assert second.status_code == 409
        assert second.json()["detail"] == "Symptom with such name already exists"

    async def test_create_symptom_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user
    ):
        cache_key = fake_get_redis.build_key("symptoms", "items", "all")
        await fake_get_redis.setc(cache_key, [{"fake": "list"}], CacheTTL.STATIC)
        assert await fake_get_redis.getc(cache_key) is not None

        response = await ac.post("/symptoms/", json=PAYLOAD)
        assert response.status_code == 201
        assert await fake_get_redis.getc(cache_key) is None

    async def test_create_symptom_unauthorized(self, ac):
        response = await ac.post("/symptoms/", json=PAYLOAD)
        assert response.status_code == 401

    async def test_create_symptom_forbidden_for_client(self, ac, fake_get_current_user):
        response = await ac.post("/symptoms/", json=PAYLOAD)
        assert response.status_code == 403


class TestReadSymptom:
    async def test_get_symptoms_success(self, ac, created_symptom):
        response = await ac.get("/symptoms/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(s["id"] == created_symptom["id"] for s in data)

    async def test_get_symptoms_cache(self, ac, fake_get_redis):
        cache_key = fake_get_redis.build_key("symptoms", "items", "all")
        assert await fake_get_redis.getc(cache_key) is None

        response = await ac.get("/symptoms/")
        assert response.status_code == 200

        cached_symptoms = await fake_get_redis.getc(cache_key)
        assert cached_symptoms is not None
        assert isinstance(cached_symptoms, list)

    async def test_get_symptom_by_id_success(self, ac, created_symptom):
        response = await ac.get(f"/symptoms/{created_symptom['id']}")
        assert response.status_code == 200

        fetched = SymptomRead.model_validate_json(response.text)
        assert fetched.id == created_symptom["id"]
        assert fetched.name == created_symptom["name"]

    async def test_get_symptom_by_id_not_found(self, ac):
        response = await ac.get("/symptoms/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Symptom not found"

    async def test_get_symptom_by_id_uses_cache(
        self, ac, fake_get_redis, created_symptom
    ):
        cache_key = fake_get_redis.build_key("symptoms", "items", "all")
        cached_symptom = {
            "id": 555,
            "name": "Cached Symptom",
            "description": "Cached Description",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        await fake_get_redis.setc(cache_key, [cached_symptom], CacheTTL.STATIC)

        response = await ac.get("/symptoms/555")
        assert response.status_code == 200
        assert response.json()["name"] == "Cached Symptom"


class TestUpdateSymptom:
    async def test_update_symptom_success(
        self, ac, get_test_session, fake_get_admin_user, created_symptom
    ):
        update_payload = {
            "name": "Updated name",
            "description": "Updated description",
        }
        response = await ac.patch(
            f"/symptoms/{created_symptom['id']}", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_symptom["id"]
        assert data["name"] == update_payload["name"]
        assert data["description"] == update_payload["description"]

        query = select(Symptom).where(Symptom.id == created_symptom["id"])
        result = await get_test_session.execute(query)
        db_symptom = result.scalar_one()
        assert db_symptom.name == update_payload["name"]
        assert db_symptom.description == update_payload["description"]

    async def test_update_symptom_empty_body(
        self, ac, fake_get_admin_user, created_symptom
    ):
        response = await ac.patch(f"/symptoms/{created_symptom['id']}", json={})
        assert response.status_code == 200
        assert response.json()["name"] == created_symptom["name"]

    async def test_update_symptom_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user, created_symptom
    ):
        cache_key = fake_get_redis.build_key("symptoms", "items", "all")
        await fake_get_redis.setc(cache_key, [created_symptom], CacheTTL.STATIC)

        response = await ac.patch(
            f"/symptoms/{created_symptom['id']}", json={"name": "New Symptom"}
        )
        assert response.status_code == 200
        assert await fake_get_redis.getc(cache_key) is None

    async def test_update_symptom_not_found(self, ac, fake_get_admin_user):
        response = await ac.patch("/symptoms/99999", json={"name": "Ghost"})
        assert response.status_code == 404

    async def test_update_symptom_unauthorized(self, ac):
        response = await ac.patch("/symptoms/1", json={"name": "Unauthorized"})
        assert response.status_code == 401

    async def test_update_symptom_forbidden_for_client(self, ac, fake_get_current_user):
        response = await ac.patch("/symptoms/1", json={"name": "Forbidden"})
        assert response.status_code == 403


class TestDeleteSymptom:
    async def test_delete_symptom_success(
        self, ac, get_test_session, fake_get_admin_user, created_symptom
    ):
        response = await ac.delete(f"/symptoms/{created_symptom['id']}")
        assert response.status_code == 204

        query = select(Symptom).where(Symptom.id == created_symptom["id"])
        result = await get_test_session.execute(query)
        assert result.scalar_one_or_none() is None

    async def test_delete_symptom_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user, created_symptom
    ):
        cache_key = fake_get_redis.build_key("symptoms", "items", "all")
        await fake_get_redis.setc(cache_key, [created_symptom], CacheTTL.STATIC)

        response = await ac.delete(f"/symptoms/{created_symptom['id']}")
        assert response.status_code == 204
        assert await fake_get_redis.getc(cache_key) is None

    async def test_delete_symptom_not_found(self, ac, fake_get_admin_user):
        response = await ac.delete("/symptoms/99999")
        assert response.status_code == 404

    async def test_delete_symptom_unauthorized(self, ac):
        response = await ac.delete("/symptoms/1")
        assert response.status_code == 401

    async def test_delete_symptom_forbidden_for_client(self, ac, fake_get_current_user):
        response = await ac.delete("/symptoms/1")
        assert response.status_code == 403
