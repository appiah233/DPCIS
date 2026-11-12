from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Isolated development/test settings that require no live external services."""
    return Settings(
        _env_file=None,
        APP_NAME="Examination Hub API",
        APP_VERSION="0.1.0",
        APP_ENV="test",
        CORS_ORIGINS=["http://localhost:5173"],
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    """FastAPI TestClient configured with isolated settings."""
    app = create_app(settings=test_settings)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
