import jwt
import pytest
from sqlalchemy import select
import datetime

from src.common.enums import UserRole
from src.core.config import settings
from src.core.security import hash_pwd, verify_pwd
from src.modules.cities.models import City
from src.modules.users.models import User
from src.common.enums import CacheTTL


@pytest.fixture
async def persisted_user(get_test_session) -> dict:
    raw_password = "test_password_secret"
    user = User(
        name="Tester",
        email="user@test.com",
        password=hash_pwd(raw_password),
        role=UserRole.CLIENT,
    )
    get_test_session.add(user)
    await get_test_session.commit()
    await get_test_session.refresh(user)

    return {
        "instance": user,
        "email": user.email,
        "raw_password": raw_password,
    }


class TestRegisterUser:
    async def test_register_user(self, ac):
        new_user = {
            "name": "Tester",
            "email": "user@test.com",
            "password": "test_password_secret",
        }
        response = await ac.post("/users/register", json=new_user)
        assert response.status_code == 201

        data = response.json()
        raw_token = data["access_token"]
        token = jwt.decode(raw_token, settings.KEY, settings.ALGORITHM)

        assert token.get("sub") == new_user["email"]
        assert token.get("exp") is not None

    async def test_register_user_with_city(self, ac, get_test_session):
        city = City(name="Novorossiysk")
        get_test_session.add(city)
        await get_test_session.commit()

        new_user = {
            "name": "Tester",
            "birth_date": "1995-10-25",
            "city_id": city.id,
            "email": "user@test.com",
            "password": "test_password_secret",
        }
        response = await ac.post("/users/register", json=new_user)
        assert response.status_code == 201

        query = select(User).where(User.email == new_user["email"])
        result = await get_test_session.execute(query)
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.name == "Tester"
        assert user.city_id == city.id
        assert user.email == "user@test.com"
        assert verify_pwd(new_user["password"], user.password)

    async def test_register_user_already_exists_error(self, ac):
        new_user = {
            "name": "Tester Mikle",
            "email": "mikle@etest.com",
            "password": "test_password_secret_mikle",
        }
        response = await ac.post("/users/register", json=new_user)
        assert response.status_code == 201

        new_user = {
            "name": "CheaterHacker",
            "email": "mikle@etest.com",
            "password": "test_parol_secret_mikle",
        }
        response = await ac.post("/users/register", json=new_user)
        assert response.status_code == 409

    async def test_register_invalid_email(self, ac):
        payload = {
            "name": "Tester",
            "email": "invalid-email-format",
            "password": "test_parol_secret",
        }
        response = await ac.post("/users/register", json=payload)
        assert response.status_code == 422

    async def test_register_invalid_password(self, ac):
        payload = {
            "name": "Tester",
            "email": "valid@test.com",
            "password": "123",
        }
        response = await ac.post("/users/register", json=payload)
        assert response.status_code == 422


class TestLoginUser:
    async def test_login_user(self, ac, persisted_user):
        payload = {
            "username": persisted_user["email"],
            "password": persisted_user["raw_password"],
        }
        response = await ac.post("/users/login", data=payload)
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_login_wrong_password(self, ac, persisted_user):
        payload = {
            "username": persisted_user["email"],
            "password": "111",
        }
        response = await ac.post("/users/login", data=payload)
        assert response.status_code == 401

    async def test_login_wrong_email(self, ac):
        payload = {
            "username": "wrong@bug.com",
            "password": "test_password_secret",
        }
        response = await ac.post("/users/login", data=payload)
        assert response.status_code == 401


class TestUserFilterParams:
    @pytest.fixture
    async def seed_users(self, get_test_session) -> list[User]:
        users = [
            User(
                name="Alice Smith",
                email="alice@test.com",
                password="pwd",
                role=UserRole.CLIENT,
                birth_date=datetime.date(1990, 1, 1),
            ),
            User(
                name="Bob Jones",
                email="bob@test.com",
                password="pwd",
                role=UserRole.DOCTOR,
                birth_date=datetime.date(1985, 5, 10),
            ),
            User(
                name="Charlie Brown",
                email="charlie@test.com",
                password="pwd",
                role=UserRole.CLIENT,
                birth_date=datetime.date(2000, 12, 12),
            ),
            User(
                name="Admin Boss",
                email="admin_user@test.com",
                password="pwd",
                role=UserRole.ADMIN,
            ),
        ]
        get_test_session.add_all(users)
        await get_test_session.commit()
        return users

    async def test_get_users_pagination_and_admin_exclusion(
        self, ac, seed_users, fake_get_admin_user
    ):
        response = await ac.get("/users/?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert all(item["role"] != UserRole.ADMIN for item in data["items"])

        response_offset = await ac.get("/users/?limit=2&offset=2")
        data_offset = response_offset.json()
        assert len(data_offset["items"]) == 1

    @pytest.mark.parametrize(
        "query_params, expected_names",
        [
            ({"name": "lice"}, ["Alice Smith"]),
            ({"email": "bob@test.com"}, ["Bob Jones"]),
            ({"role": UserRole.DOCTOR.value}, ["Bob Jones"]),
            ({"birth_date": "2000-12-12"}, ["Charlie Brown"]),
        ],
    )
    async def test_get_users_filters(
        self, ac, seed_users, fake_get_admin_user, query_params, expected_names
    ):
        response = await ac.get("/users/", params=query_params)
        assert response.status_code == 200
        data = response.json()

        result_names = [user["name"] for user in data["items"]]
        assert result_names == expected_names


class TestUserById:
    async def test_get_user_by_id(self, ac, persisted_user, fake_get_admin_user):
        user_id = persisted_user["instance"].id
        assert user_id is not None
        response = await ac.get(f"/users/{user_id}")

        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Tester"
        assert data["email"] == "user@test.com"

    async def test_get_user_by_id_not_found_error(
        self, ac, persisted_user, fake_get_admin_user
    ):
        response = await ac.get("/users/9999")
        assert response.status_code == 404

    async def test_get_user_by_id_access_error(self, ac, persisted_user):
        response = await ac.get("/users/1")
        assert response.status_code == 401


class TestUserMe:
    async def test_get_me(self, ac, fake_get_current_user):
        response = await ac.get("/users/me")
        data = response.json()

        assert response.status_code == 200
        assert data["name"] == "TestUser"
        assert data["email"] == "user@test.com"

    async def test_get_me_not_authorized(self, ac):
        response = await ac.get("/users/me")
        assert response.status_code == 401


class TestUpdatreUser:
    async def test_update_user_basic(self, ac, fake_get_current_user):
        assert fake_get_current_user.email == "user@test.com"
        assert fake_get_current_user.birth_date is None
        assert fake_get_current_user.name == "TestUser"

        update_data = {
            "birth_date": "1995-10-25",
            "name": "UpdatedUser",
        }
        response = await ac.patch("/users/me", json=update_data)
        data = response.json()

        assert data["birth_date"] == "1995-10-25"
        assert data["name"] == "UpdatedUser"

    async def test_update_user_access_error(self, ac):
        update_data = {
            "birth_date": "1995-10-25",
            "name": "UpdatedUser",
        }
        response = await ac.patch("/users/me", json=update_data)
        assert response.status_code == 401

    async def test_update_user_cache(self, ac, fake_get_current_user, fake_get_redis):
        cache_key = fake_get_redis.build_key(
            "users", "current", fake_get_current_user.email
        )
        await fake_get_redis.setc(cache_key, fake_get_current_user, CacheTTL.FAST)

        cached_user = await fake_get_redis.getc(cache_key)
        assert cached_user is not None

        update_data = {
            "birth_date": "1995-10-25",
            "name": "UpdatedUser",
        }
        await ac.patch("/users/me", json=update_data)

        cached_user = await fake_get_redis.getc(cache_key)
        assert cached_user is None


class TestUpdatrePassword:
    async def test_update_user_password(
        self, ac, fake_get_current_user, get_test_session
    ):
        update_data = {
            "old_password": "test_hashed_password",
            "new_password": "new_password_update",
        }
        await ac.patch("/users/me/password", json=update_data)

        query = select(User.password).where(User.id == fake_get_current_user.id)
        result = await get_test_session.execute(query)
        user_password = result.scalar_one_or_none()

        assert verify_pwd("new_password_update", user_password)

    async def test_update_user_incorrect_password(self, ac, fake_get_current_user):
        update_data = {
            "old_password": "wrong_password",
            "new_password": "new_password_update",
        }
        response = await ac.patch("/users/me/password", json=update_data)
        assert response.status_code == 400

    async def test_update_user_cache(self, ac, fake_get_current_user, fake_get_redis):
        cache_key = fake_get_redis.build_key(
            "users", "current", fake_get_current_user.email
        )
        await fake_get_redis.setc(cache_key, fake_get_current_user, CacheTTL.FAST)

        cached_user = await fake_get_redis.getc(cache_key)
        assert cached_user is not None

        update_data = {
            "old_password": "test_hashed_password",
            "new_password": "new_password_update",
        }
        await ac.patch("/users/me/password", json=update_data)

        cached_user = await fake_get_redis.getc(cache_key)
        assert cached_user is None


class TestDeleteUser:
    async def test_delete_user(self, ac, fake_get_current_user, get_test_session):
        delete_data = {"password": "test_hashed_password"}
        response = await ac.request("DELETE", "/users/me", json=delete_data)
        assert response.status_code == 204

        query = select(User).where(User.id == fake_get_current_user.id)
        result = await get_test_session.execute(query)
        user = result.scalar_one_or_none()

        assert user is None

    async def test_delete_user_incorrect_password(self, ac, fake_get_current_user):
        delete_data = {"password": "wrong_password"}
        response = await ac.request("DELETE", "/users/me", json=delete_data)
        assert response.status_code == 400

    async def test_delete_user_cache(self, ac, fake_get_current_user, fake_get_redis):
        cache_key = fake_get_redis.build_key(
            "users", "current", fake_get_current_user.email
        )
        await fake_get_redis.setc(cache_key, fake_get_current_user, CacheTTL.FAST)

        cached_user = await fake_get_redis.getc(cache_key)
        assert cached_user is not None

        delete_data = {"password": "test_hashed_password"}
        response = await ac.request("DELETE", "/users/me", json=delete_data)
        assert response.status_code == 204

        cached_user = await fake_get_redis.getc(cache_key)
        assert cached_user is None
