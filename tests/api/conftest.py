import pytest


@pytest.fixture(scope="session", autouse=True)
async def prepare_api_database(prepare_database):
    yield


@pytest.fixture(autouse=True)
async def clean_api_database(clean_database):
    yield
