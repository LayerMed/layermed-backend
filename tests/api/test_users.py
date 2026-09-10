
import jwt
import pytest
from sqlalchemy import select

from src.common.enums import UserRole
from src.core.config import settings
from src.core.security import hash_pwd, verify_pwd
from src.modules.cities.models import City
from src.modules.users.models import User


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

    return {
        "instance": user,
        "email": user.email,
        "raw_password": raw_password,
    }


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
