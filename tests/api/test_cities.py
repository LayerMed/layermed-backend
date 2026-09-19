import pytest
from sqlalchemy import select

from src.common.enums import CacheTTL
from src.modules.cities.models import City
from src.modules.cities.schemas import CityRead

NAME = "Pennsylvania"
PAYLOAD = {"name": NAME}


@pytest.fixture
async def created_city(ac, fake_get_admin_user):
    response = await ac.post("/cities/", json=PAYLOAD)
    assert response.status_code == 201
    return response.json()


class TestCreateCity:
    async def test_create_city_success(self, ac, get_test_session, fake_get_admin_user):
        response = await ac.post("/cities/", json=PAYLOAD)
        assert response.status_code == 201
        data = response.json()

        assert data["id"] is not None
        assert data["name"] == NAME

        query = select(City).where(City.id == data["id"])
        result = await get_test_session.execute(query)
        assert result.scalar_one_or_none() is not None

    async def test_create_city_validation_error(self, ac, fake_get_admin_user):
        long_payload = {"name": "Long" * 100}
        response = await ac.post("/cities/", json=long_payload)
        assert response.status_code == 422

    async def test_create_city_already_exists_error(self, ac, fake_get_admin_user):
        first = await ac.post("/cities/", json=PAYLOAD)
        assert first.status_code == 201

        second = await ac.post("/cities/", json=PAYLOAD)
        assert second.status_code == 409
        assert second.json()["detail"] == "City with this name already exists"

    async def test_create_city_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user
    ):
        cache_key = fake_get_redis.build_key("cities", "items", "all")
        await fake_get_redis.setc(cache_key, [{"fake": "list"}], CacheTTL.STATIC)
        assert await fake_get_redis.getc(cache_key) is not None

        response = await ac.post("/cities/", json=PAYLOAD)
        assert response.status_code == 201
        assert await fake_get_redis.getc(cache_key) is None

    async def test_create_city_unauthorized(self, ac):
        response = await ac.post("/cities/", json=PAYLOAD)
        assert response.status_code == 401

    async def test_create_city_forbidden_for_client(self, ac, fake_get_current_user):
        response = await ac.post("/cities/", json=PAYLOAD)
        assert response.status_code == 403


class TestReadCity:
    async def test_get_cities_success(self, ac, created_city):
        response = await ac.get("/cities/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(c["id"] == created_city["id"] for c in data)

    async def test_get_cities_cache(self, ac, fake_get_redis):
        cache_key = fake_get_redis.build_key("cities", "items", "all")
        assert await fake_get_redis.getc(cache_key) is None

        response = await ac.get("/cities/")
        assert response.status_code == 200

        cached_cities = await fake_get_redis.getc(cache_key)
        assert cached_cities is not None
        assert isinstance(cached_cities, list)

    async def test_get_city_by_id_success(self, ac, created_city):
        response = await ac.get(f"/cities/{created_city['id']}")
        assert response.status_code == 200

        fetched_city = CityRead.model_validate_json(response.text)
        assert fetched_city.id == created_city["id"]
        assert fetched_city.name == created_city["name"]

    async def test_get_city_by_id_not_found(self, ac):
        response = await ac.get("/cities/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "City not found"

    async def test_get_city_by_id_uses_cache(self, ac, fake_get_redis, created_city):
        cache_key = fake_get_redis.build_key("cities", "items", "all")
        cached_city = {
            "id": 777,
            "name": "Cached City",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        await fake_get_redis.setc(cache_key, [cached_city], CacheTTL.STATIC)

        response = await ac.get("/cities/777")
        assert response.status_code == 200
        assert response.json()["name"] == "Cached City"


class TestUpdateCity:
    async def test_update_city_success(
        self, ac, get_test_session, fake_get_admin_user, created_city
    ):
        update_payload = {"name": "Updated Name"}
        response = await ac.patch(f"/cities/{created_city['id']}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_city["id"]
        assert data["name"] == update_payload["name"]

        query = select(City).where(City.id == created_city["id"])
        result = await get_test_session.execute(query)
        db_city = result.scalar_one()
        assert db_city.name == update_payload["name"]

    async def test_update_city_empty_body(self, ac, fake_get_admin_user, created_city):
        response = await ac.patch(f"/cities/{created_city['id']}", json={})
        assert response.status_code == 200
        assert response.json()["name"] == created_city["name"]

    async def test_update_city_conflict_error(
        self, ac, fake_get_admin_user, created_city
    ):
        other_city = {"name": "Second City"}
        res = await ac.post("/cities/", json=other_city)
        assert res.status_code == 201

        response = await ac.patch(
            f"/cities/{created_city['id']}", json={"name": "Second City"}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "City with this name already exists"

    async def test_update_city_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user, created_city
    ):
        cache_key = fake_get_redis.build_key("cities", "items", "all")
        await fake_get_redis.setc(cache_key, [created_city], CacheTTL.STATIC)

        response = await ac.patch(
            f"/cities/{created_city['id']}", json={"name": "Another Name"}
        )
        assert response.status_code == 200
        assert await fake_get_redis.getc(cache_key) is None

    async def test_update_city_not_found(self, ac, fake_get_admin_user):
        response = await ac.patch("/cities/99999", json={"name": "Ghost City"})
        assert response.status_code == 404

    async def test_update_city_unauthorized(self, ac, created_city):
        response = await ac.patch(
            f"/cities/{created_city['id']}", json={"name": "Unauthorized"}
        )
        assert response.status_code == 401

    async def test_update_city_forbidden_for_client(
        self, ac, fake_get_current_user, created_city
    ):
        response = await ac.patch(
            f"/cities/{created_city['id']}", json={"name": "Forbidden"}
        )
        assert response.status_code == 403


class TestDeleteCity:
    async def test_delete_city_success(
        self, ac, get_test_session, fake_get_admin_user, created_city
    ):
        response = await ac.delete(f"/cities/{created_city['id']}")
        assert response.status_code == 204

        query = select(City).where(City.id == created_city["id"])
        result = await get_test_session.execute(query)
        assert result.scalar_one_or_none() is None

    async def test_delete_city_invalidates_cache(
        self, ac, fake_get_redis, fake_get_admin_user, created_city
    ):
        cache_key = fake_get_redis.build_key("cities", "items", "all")
        await fake_get_redis.setc(cache_key, [created_city], CacheTTL.STATIC)

        response = await ac.delete(f"/cities/{created_city['id']}")
        assert response.status_code == 204
        assert await fake_get_redis.getc(cache_key) is None

    async def test_delete_city_not_found(self, ac, fake_get_admin_user):
        response = await ac.delete("/cities/99999")
        assert response.status_code == 404

    async def test_delete_city_unauthorized(self, ac, created_city):
        response = await ac.delete(f"/cities/{created_city['id']}")
        assert response.status_code == 401

    async def test_delete_city_forbidden_for_client(
        self, ac, fake_get_current_user, created_city
    ):
        response = await ac.delete(f"/cities/{created_city['id']}")
        assert response.status_code == 403
