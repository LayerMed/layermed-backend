import pytest
from sqlalchemy import select

from src.common.enums import CacheTTL
from src.modules.cities.models import City
from src.modules.cities.schemas import CityCreate, CityRead, CityUpdate

name = "Pennsylvania"
payload = {
    "name": name,    
}


@pytest.fixture
async def created_city(ac, fake_get_admin_user):
    response = await ac.post("/cities/", json=payload)
    assert response.status_code == 201
    return response.json()


class TestCreateCity:
    async def test_create_city(self, ac, get_test_session, fake_get_admin_user):
        response = await ac.post("/cities/", json=payload)
        data = response.json()

        assert response.status_code == 201
        assert data["id"] is not None
        assert data["name"] == name        

        query = select(City).where(City.id == data["id"])
        city = await get_test_session.execute(query)
        assert city.scalar_one_or_none() is not None

    async def test_create_city_validation_error(self, ac, fake_get_admin_user):
        long_payload = {
            "name": "This text contains more than 100 characters to fully satisfy your request. Writing a short paragraph in English makes it easy to quickly reach and exceed this specific length requirement while keeping the message clear and simple.",
        }
        response = await ac.post("/cities/", json=long_payload)
        assert response.status_code == 422

    async def test_create_city_already_exists_error(self, ac, fake_get_admin_user):
        first = await ac.post("/cities/", json=payload)
        assert first.status_code == 201

        second = await ac.post("/cities/", json=payload)
        assert second.status_code == 409

    async def test_create_city_cache(self, ac, fake_get_redis, fake_get_admin_user):
        cache_key = fake_get_redis.build_key("cities", "items", "all")

        await fake_get_redis.setc(
            cache_key, CityCreate.model_validate(payload), CacheTTL.STATIC
        )

        cached_cities = await fake_get_redis.getc(cache_key)
        assert cached_cities is not None

        await ac.post("/cities/", json=payload)
        cached_cities = await fake_get_redis.getc(cache_key)
        assert cached_cities is None

    async def test_create_city_access(self, ac):
        response = await ac.post("/cities/", json=payload)
        assert response.status_code == 401


class TestReadCity:
    async def test_get_cities(self, ac, created_city, get_test_session):
        response = await ac.get("/cities/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_cities_cache(self, ac, fake_get_redis):
        cache_key = fake_get_redis.build_key("cities", "items", "all")

        cached_cities = await fake_get_redis.getc(cache_key)
        assert cached_cities is None

        response = await ac.get("/cities/")
        assert response.status_code == 200

        cached_cities = await fake_get_redis.getc(cache_key)
        assert cached_cities is not None

    async def test_get_city_by_id(self, ac, created_city):
        response_get = await ac.get(f"/cities/{created_city['id']}")
        assert response_get.status_code == 200

        fetched_city = CityRead.model_validate_json(response_get.text)
        assert fetched_city.id == created_city["id"]

    async def test_get_city_by_id_not_found_error(self, ac):
        response_get = await ac.get("/cities/9999")
        assert response_get.status_code == 404

    async def test_get_city_by_id_cache(self, ac, fake_get_redis, created_city):

        cache_key = fake_get_redis.build_key("cities", "items", "all")

        cached_cities = await fake_get_redis.getc(cache_key)
        assert cached_cities is None

        response_get = await ac.get(f"/cities/{created_city['id']}")
        assert response_get.status_code == 200

        cached_cities = await fake_get_redis.getc(cache_key)
        assert cached_cities is not None


class TestUpadteCity:
    async def test_update_city(self, ac, get_test_session, created_city):
        update_payload = {
            "name": "Updated name"
        }

        response_update = await ac.patch(
            f"/cities/{created_city['id']}", json=update_payload
        )

        assert response_update.status_code == 200
        data_updated = response_update.json()
        assert data_updated["id"] == created_city["id"]
        assert data_updated["name"] == update_payload["name"]        

        query = select(City).where(City.id == created_city["id"])
        result = await get_test_session.execute(query)
        db_city = result.scalar_one()

        assert db_city.name == update_payload["name"]        

    async def test_update_city_cache(self, ac, fake_get_redis, created_city):
        update_payload = {
            "name": "Updated name",            
        }
        cache_key = fake_get_redis.build_key("cities", "items", "all")

        await fake_get_redis.setc(cache_key, payload, CacheTTL.STATIC)

        cached_city = await fake_get_redis.getc(cache_key)
        assert cached_city is not None

        await ac.patch(f"/cities/{created_city['id']}", json=update_payload)

        cached_city = await fake_get_redis.getc(cache_key)
        assert cached_city is None

    async def test_update_city_not_found_error(self, ac, fake_get_admin_user):
        response = await ac.patch("/cities/9999", json=payload)
        assert response.status_code == 404


class TestDeletecity:
    async def test_delete_city(self, ac, created_city):
        response = await ac.delete(f"/cities/{created_city['id']}")
        assert response.status_code == 204

    async def test_delete_city_cache(self, ac, fake_get_redis, created_city):
        cache_key = fake_get_redis.build_key("cities", "items", "all")

        await fake_get_redis.setc(cache_key, payload, CacheTTL.STATIC)

        cached_city = await fake_get_redis.getc(cache_key)
        assert cached_city is not None

        await ac.delete(f"/cities/{created_city['id']}")

        cached_city = await fake_get_redis.getc(cache_key)
        assert cached_city is None

    async def test_delete_city_not_found_error(self, ac, fake_get_admin_user):
        response = await ac.delete("/cities/9999")
        assert response.status_code == 404
