from src.core.security import hash_pwd, verify_pwd, create_access_token
from src.core.config import settings
from datetime import datetime, timezone

import pytest
import jwt


class TestHashPwd:
    def test_hash_pwd(self):
        pwd = "secretpwd123"
        assert hash_pwd(pwd) != pwd 


    @pytest.mark.parametrize(
        "pwd",
        [
            "secretpwd123",
            "123",
            "helloheybye",
            "jkvnsv;nlfkdv",
        ]
    )
    def test_salt_hash_pwd(self, pwd: str):
        assert hash_pwd(pwd) != hash_pwd(pwd)


    def test_error_hash_pwd(self):
        with pytest.raises(TypeError):
            hash_pwd(123)


class TestVerifyPwd:
    def test_verify_pwd(self):
        pwd = "secretpwd123"
        hashed_pwd = hash_pwd(pwd)

        assert verify_pwd(pwd, hashed_pwd) is True


    def test_wrong_verify_pwd(self):
        pwd = "secretpwd123"
        hashed_pwd = hash_pwd(pwd)

        assert verify_pwd("wrongpwd321", hashed_pwd) is False


    def test_error_verify_pwd(self):
        pwd = "secretpwd123"
        hashed_pwd = hash_pwd(pwd)

        with pytest.raises(TypeError):
            verify_pwd(123, hashed_pwd)


class TestAccessToken:
    def test_create_access_token(self):
        test_email = "test@example.com"

        token = create_access_token(
            {"sub": test_email}
        )

        decoded_token = jwt.decode(token, settings.KEY, algorithms=settings.ALGORITHM)
        
        assert decoded_token.get("sub") == test_email 
        assert isinstance(decoded_token.get("exp"), int)


    def test_token_expiration_in_future(self):
        token = create_access_token(
            {"sub": "test@example.com"}
        )
        decoded_token = jwt.decode(token, settings.KEY, algorithms=settings.ALGORITHM)

        exp = decoded_token.get("exp")
        now_timestamp = datetime.now(timezone.utc).timestamp()
        assert exp > now_timestamp


