import pytest
from pydantic import ValidationError

from app.config import ConfigurationError, Settings


def test_development_defaults_load_predictably_without_external_secrets() -> None:
    settings = Settings(_env_file=None)

    assert settings.APP_NAME == "Examination Hub API"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.APP_ENV == "development"
    assert settings.CORS_ORIGINS == ["http://localhost:5173"]
    assert settings.DATABASE_URL is None
    assert settings.NEON_AUTH_BASE_URL is None


def test_cors_origins_parses_comma_separated_and_strips_trailing_slashes() -> None:
    settings = Settings(
        _env_file=None,
        CORS_ORIGINS="https://app.example.com/, https://admin.example.com ",
    )

    assert settings.CORS_ORIGINS == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


@pytest.mark.parametrize(
    "invalid_kwargs",
    [
        {"APP_NAME": "   "},
        {"APP_ENV": "qa"},
        {"LOG_LEVEL": "VERBOSE"},
        {"CORS_ORIGINS": ["*"]},
        {"CORS_ORIGINS": ["not-a-url"]},
        {"DATABASE_URL": "mysql://user:pass@localhost/db"},
        {"DATABASE_URL": "sqlite:///./local.db", "APP_ENV": "development"},
        {"NEON_AUTH_JWKS_URL": "http://insecure.example.com/.well-known/jwks.json"},
        {"NEON_AUTH_BASE_URL": "http://insecure.example.com"},
    ],
)
def test_invalid_configuration_fails_predictably(invalid_kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **invalid_kwargs)


@pytest.mark.parametrize("env_name", ["staging", "production"])
def test_deployed_environments_require_database_and_neon_auth_config(env_name: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            APP_ENV=env_name,
            CORS_ORIGINS=["https://exams.example.com"],
        )

    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert "NEON_AUTH_BASE_URL" in message
    assert "NEON_AUTH_JWKS_URL" in message


def test_production_rejects_wildcard_or_localhost_cors_origins() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="production",
            CORS_ORIGINS=["http://localhost:5173"],
            DATABASE_URL="postgresql://user:pass@ep-demo.neon.tech/db?sslmode=require",
            NEON_AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
            NEON_AUTH_BASE_URL="https://auth.example.com",
        )


def test_required_boundary_helpers_raise_clear_configuration_errors_when_unset() -> None:
    settings = Settings(_env_file=None, APP_ENV="development")

    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        settings.require_database_url()

    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        settings.require_migration_database_url()

    with pytest.raises(ConfigurationError, match="NEON_AUTH_JWKS_URL"):
        settings.require_neon_auth_config()


def test_secret_values_are_masked_in_settings_repr() -> None:
    fake_db = "postgresql://user:super_secret_pw@ep-demo.neon.tech/neondb?sslmode=require"
    settings = Settings(
        _env_file=None,
        DATABASE_URL=fake_db,
        NEON_AUTH_BASE_URL="https://auth.example.com",
        NEON_AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
    )

    rendered = repr(settings)
    assert "super_secret_pw" not in rendered
    assert "https://auth.example.com" in rendered
    assert settings.require_database_url() == fake_db
