import datetime

import jwt
import pytest
from sqlalchemy import select

from src.common.enums import CacheTTL, UserRole
from src.core.config import settings
from src.core.security import verify_pwd
from src.modules.users.models import User


class TestRegisterUser:
    async def test_register_user_success(self, ac):
        new_user = {
            "name": "Tester",
            "email": "user_reg@test.com",
            "password": "TestPassword123!Secure",
        }
        response = await ac.post("/users/register", json=new_user)
        assert response.status_code == 201

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in response.cookies

        token = jwt.decode(
            data["access_token"],
            settings.KEY,
            algorithms=[settings.ALGORITHM],
        )
        assert token.get("sub") == new_user["email"]
        assert token.get("exp") is not None

    async def test_register_user_with_city(self, ac, get_test_session, seed_city):
        new_user = {
            "name": "Tester",
            "birth_date": "1995-10-25",
            "city_id": seed_city.id,
            "email": "user_city@test.com",
            "password": "TestPassword123!Secure",
        }
        response = await ac.post("/users/register", json=new_user)
        assert response.status_code == 201

        query = select(User).where(User.email == new_user["email"])
        result = await get_test_session.execute(query)
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.city_id == seed_city.id
        assert user.birth_date == datetime.date(1995, 10, 25)
        assert verify_pwd(new_user["password"], user.password)

    async def test_register_user_already_exists_error(
        self, ac, user_factory, get_test_session
    ):
        await user_factory(email="existing@test.com")
        await get_test_session.commit()

        new_user = {
            "name": "Cheater",
            "email": "existing@test.com",
            "password": "TestPassword123!Secure",
        }
        response = await ac.post("/users/register", json=new_user)
        assert response.status_code == 409
        assert response.json()["detail"] == "User with this email already exists"

    async def test_register_invalid_email(self, ac):
        payload = {
            "name": "Tester",
            "email": "not-an-email",
            "password": "TestPassword123!Secure",
        }
        response = await ac.post("/users/register", json=payload)
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "invalid_password",
        [
            "123",
            "password",
            "aaaaaaaaaa",
            "qwerty12345",
        ],
    )
    async def test_register_weak_passwords(self, ac, invalid_password):
        payload = {
            "name": "Tester",
            "email": "valid@test.com",
            "password": invalid_password,
        }
        response = await ac.post("/users/register", json=payload)
        assert response.status_code == 422


class TestLoginUser:
    async def test_login_user_success(self, ac, get_test_session, user_factory):
        raw_password = "TestPassword123!Secure"
        user = await user_factory(
            email="login_user@test.com",
            password=raw_password,
        )
        await get_test_session.commit()

        payload = {
            "username": user.email,
            "password": raw_password,
        }
        response = await ac.post("/users/login", data=payload)
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert "refresh_token" in response.cookies

    async def test_login_wrong_password(self, ac, get_test_session, user_factory):
        user = await user_factory(
            email="wrong_pwd@test.com",
            password="TestPassword123!Secure",
        )
        await get_test_session.commit()

        payload = {
            "username": user.email,
            "password": "CompletelyWrongPassword123!",
        }
        response = await ac.post("/users/login", data=payload)
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    async def test_login_wrong_email(self, ac):
        payload = {
            "username": "non_existent@test.com",
            "password": "TestPassword123!Secure",
        }
        response = await ac.post("/users/login", data=payload)
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"


class TestSessionManagement:
    async def test_refresh_token_success(
        self, ac, fake_get_redis, get_test_session, user_factory
    ):
        user = await user_factory(email="refresh_me@test.com")
        await get_test_session.commit()

        refresh_token = "valid_refresh_token_uuid"
        refresh_key = fake_get_redis.build_key("users", "refresh", refresh_token)
        await fake_get_redis.setc(refresh_key, user.email, ex=CacheTTL.FAST)

        ac.cookies.set("refresh_token", refresh_token)
        response = await ac.post("/users/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in response.cookies

        assert await fake_get_redis.getc(refresh_key) is None

    async def test_refresh_token_missing_cookie(self, ac):
        response = await ac.post("/users/refresh")
        assert response.status_code == 401
        assert response.json()["detail"] == "Refresh token missing"

    async def test_refresh_token_invalid_or_expired(self, ac):
        ac.cookies.set("refresh_token", "expired_token")
        response = await ac.post("/users/refresh")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired refresh token"

    async def test_logout_revokes_token_and_deletes_cookie(self, ac, fake_get_redis):
        refresh_token = "token_to_revoke"
        refresh_key = fake_get_redis.build_key("users", "refresh", refresh_token)
        await fake_get_redis.setc(refresh_key, "user@test.com", ex=CacheTTL.FAST)

        ac.cookies.set("refresh_token", refresh_token)
        response = await ac.post("/users/logout")
        assert response.status_code == 204
        assert await fake_get_redis.getc(refresh_key) is None


class TestUserFilterParams:
    @pytest.fixture
    async def seed_users(self, get_test_session, user_factory):
        u1 = await user_factory(
            name="Alice Smith",
            email="alice@test.com",
            role=UserRole.CLIENT,
            birth_date=datetime.date(1990, 1, 1),
        )
        u2 = await user_factory(
            name="Bob Jones",
            email="bob@test.com",
            role=UserRole.DOCTOR,
            birth_date=datetime.date(1985, 5, 10),
        )
        u3 = await user_factory(
            name="Charlie Brown",
            email="charlie@test.com",
            role=UserRole.CLIENT,
            birth_date=datetime.date(2000, 12, 12),
        )
        admin = await user_factory(
            name="Admin Boss",
            email="admin_in_list@test.com",
            role=UserRole.ADMIN,
        )
        await get_test_session.commit()
        return [u1, u2, u3, admin]

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

    async def test_get_users_forbidden_for_client(self, ac, fake_get_current_user):
        response = await ac.get("/users/")
        assert response.status_code == 403


class TestUserById:
    async def test_get_user_by_id_success(
        self, ac, fake_get_admin_user, user_factory, get_test_session
    ):
        user = await user_factory(name="Target User", email="target@test.com")
        await get_test_session.commit()

        response = await ac.get(f"/users/{user.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user.id
        assert data["name"] == "Target User"
        assert data["email"] == "target@test.com"

    async def test_get_user_by_id_not_found_error(self, ac, fake_get_admin_user):
        response = await ac.get("/users/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    async def test_get_user_by_id_access_error(self, ac, fake_get_current_user):
        response = await ac.get("/users/1")
        assert response.status_code == 403


class TestUserMe:
    async def test_get_me_success(self, ac, fake_get_current_user):
        response = await ac.get("/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == fake_get_current_user.id
        assert data["name"] == fake_get_current_user.name
        assert data["email"] == fake_get_current_user.email

    async def test_get_me_not_authorized(self, ac):
        response = await ac.get("/users/me")
        assert response.status_code == 401


class TestUpdateUser:
    async def test_update_user_basic(self, ac, fake_get_current_user):
        update_data = {
            "birth_date": "1995-10-25",
            "name": "UpdatedUser",
        }
        response = await ac.patch("/users/me", json=update_data)
        assert response.status_code == 200
        data = response.json()

        assert data["birth_date"] == "1995-10-25"
        assert data["name"] == "UpdatedUser"

    async def test_update_user_empty_body(self, ac, fake_get_current_user):
        response = await ac.patch("/users/me", json={})
        assert response.status_code == 200
        assert response.json()["id"] == fake_get_current_user.id

    async def test_update_user_access_error(self, ac):
        response = await ac.patch("/users/me", json={"name": "NoAuth"})
        assert response.status_code == 401

    async def test_update_user_invalidates_cache(
        self, ac, fake_get_current_user, fake_get_redis
    ):
        cache_key = fake_get_redis.build_key(
            "users", "current", fake_get_current_user.email
        )
        await fake_get_redis.setc(cache_key, fake_get_current_user, CacheTTL.FAST)
        assert await fake_get_redis.getc(cache_key) is not None

        await ac.patch("/users/me", json={"name": "NewName"})
        assert await fake_get_redis.getc(cache_key) is None


class TestUpdatePassword:
    async def test_update_user_password_success(
        self, ac, fake_get_current_user, get_test_session
    ):
        update_data = {
            "old_password": "test_hashed_password",
            "new_password": "NewSecretPassword123!Secure",
        }
        response = await ac.patch("/users/me/password", json=update_data)
        assert response.status_code == 200
        assert response.json()["message"] == "Password successfully updated"

        query = select(User).where(User.id == fake_get_current_user.id)
        result = await get_test_session.execute(query)
        user = result.scalar_one()

        assert verify_pwd("NewSecretPassword123!Secure", user.password)
        assert user.token_version == fake_get_current_user.token_version + 1

    async def test_update_user_incorrect_password(self, ac, fake_get_current_user):
        update_data = {
            "old_password": "wrong_password",
            "new_password": "NewSecretPassword123!Secure",
        }
        response = await ac.patch("/users/me/password", json=update_data)
        assert response.status_code == 400
        assert response.json()["detail"] == "Incorrect password"

    async def test_update_user_password_invalidates_cache(
        self, ac, fake_get_current_user, fake_get_redis
    ):
        cache_key = fake_get_redis.build_key(
            "users", "current", fake_get_current_user.email
        )
        await fake_get_redis.setc(cache_key, fake_get_current_user, CacheTTL.FAST)

        update_data = {
            "old_password": "test_hashed_password",
            "new_password": "NewSecretPassword123!Secure",
        }
        await ac.patch("/users/me/password", json=update_data)
        assert await fake_get_redis.getc(cache_key) is None


class TestDeleteUser:
    async def test_delete_user_client_success(
        self, ac, fake_get_current_user, get_test_session, fake_get_redis
    ):
        cache_key = fake_get_redis.build_key(
            "users", "current", fake_get_current_user.email
        )
        await fake_get_redis.setc(cache_key, fake_get_current_user, CacheTTL.FAST)

        delete_data = {"password": "test_hashed_password"}
        response = await ac.request("DELETE", "/users/me", json=delete_data)
        assert response.status_code == 204

        query = select(User).where(User.id == fake_get_current_user.id)
        result = await get_test_session.execute(query)
        assert result.scalar_one_or_none() is None
        assert await fake_get_redis.getc(cache_key) is None

    async def test_delete_user_doctor_invalidates_related_caches(
        self, ac, fake_get_current_user_as_doctor, get_test_session, fake_get_redis
    ):
        doc_cache_key = fake_get_redis.build_key("doctors", "items", "all")
        offer_cache_key = fake_get_redis.build_key("offers", "items", "all")
        await fake_get_redis.setc(doc_cache_key, [{"fake": "doctor"}], CacheTTL.FAST)
        await fake_get_redis.setc(offer_cache_key, [{"fake": "offer"}], CacheTTL.FAST)

        delete_data = {"password": "test_hashed_password"}
        response = await ac.request("DELETE", "/users/me", json=delete_data)
        assert response.status_code == 204

        assert await fake_get_redis.getc(doc_cache_key) is None
        assert await fake_get_redis.getc(offer_cache_key) is None

    async def test_delete_user_incorrect_password(self, ac, fake_get_current_user):
        delete_data = {"password": "wrong_password"}
        response = await ac.request("DELETE", "/users/me", json=delete_data)
        assert response.status_code == 400
        assert response.json()["detail"] == "Incorrect password"
