import json
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_ALLOWED_PG_SCHEMES = {"postgres", "postgresql", "postgresql+psycopg"}


class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


def _parse_origin_list(value: object, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{field_name} contains invalid JSON list syntax") from exc
            if not isinstance(parsed, list):
                raise ValueError(f"{field_name} JSON value must be a list of origins")
            raw_items = [str(item) for item in parsed]
        else:
            raw_items = stripped.split(",")
    elif isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raise ValueError(f"{field_name} must be a list or comma-separated string")

    cleaned: list[str] = []
    for item in raw_items:
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        if origin == "*":
            raise ValueError(f"{field_name} must not contain wildcard '*'")
        parsed_url = urlparse(origin)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(f"{field_name} contains invalid origin: {origin}")
        cleaned.append(origin)
    return cleaned


def _unwrap_secret(value: object) -> str | None:
    if value is None:
        return None
    raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
    cleaned = raw.strip()
    return cleaned or None


def _validate_https_url(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field_name} must be a valid https:// URL")
    return cleaned


class Settings(BaseSettings):
    """Environment-driven application configuration."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "Examination Hub API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: AppEnv = "development"
    LOG_LEVEL: LogLevel = "INFO"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    DATABASE_URL: SecretStr | None = None
    DIRECT_DATABASE_URL: SecretStr | None = None

    NEON_AUTH_BASE_URL: str | None = None
    NEON_AUTH_JWKS_URL: str | None = None
    NEON_AUTH_AUDIENCE: str | None = None

    @field_validator("APP_NAME", "APP_VERSION", mode="before")
    @classmethod
    def _validate_non_empty_text(cls, value: object, info) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{info.field_name} must not be empty")
        return text

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _validate_cors_origins(cls, value: object) -> list[str]:
        return _parse_origin_list(value, field_name="CORS_ORIGINS")

    @field_validator("DATABASE_URL", "DIRECT_DATABASE_URL", mode="before")
    @classmethod
    def _normalize_optional_secret(cls, value: object) -> SecretStr | None:
        raw = _unwrap_secret(value)
        return SecretStr(raw) if raw is not None else None

    @field_validator("NEON_AUTH_BASE_URL", "NEON_AUTH_JWKS_URL", mode="before")
    @classmethod
    def _validate_neon_auth_urls(cls, value: object, info) -> str | None:
        if value is None:
            return None
        return _validate_https_url(str(value), field_name=info.field_name)

    @field_validator("NEON_AUTH_AUDIENCE", mode="before")
    @classmethod
    def _normalize_optional_str(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def _validate_environment_invariants(self) -> "Settings":
        for field_name, secret_val in (
            ("DATABASE_URL", self.DATABASE_URL),
            ("DIRECT_DATABASE_URL", self.DIRECT_DATABASE_URL),
        ):
            if secret_val is None:
                continue
            raw_url = secret_val.get_secret_value()
            scheme = raw_url.split("://", 1)[0].lower() if "://" in raw_url else ""
            if scheme == "sqlite":
                if self.APP_ENV != "test":
                    raise ValueError(
                        f"{field_name} cannot use sqlite when APP_ENV={self.APP_ENV!r}"
                    )
            elif scheme not in _ALLOWED_PG_SCHEMES:
                allowed = ", ".join(sorted(_ALLOWED_PG_SCHEMES))
                raise ValueError(
                    f"{field_name} must use a PostgreSQL scheme ({allowed})"
                )

        if self.APP_ENV in {"staging", "production"}:
            missing: list[str] = []
            if self.DATABASE_URL is None:
                missing.append("DATABASE_URL")
            if self.NEON_AUTH_BASE_URL is None:
                missing.append("NEON_AUTH_BASE_URL")
            if self.NEON_AUTH_JWKS_URL is None:
                missing.append("NEON_AUTH_JWKS_URL")
            if missing:
                raise ValueError(
                    f"Missing required settings for APP_ENV={self.APP_ENV!r}: {', '.join(missing)}"
                )
            for origin in self.CORS_ORIGINS:
                parsed = urlparse(origin)
                if parsed.hostname in {"localhost", "127.0.0.1"} or parsed.scheme != "https":
                    raise ValueError(
                        f"CORS_ORIGINS in {self.APP_ENV!r} must use https:// non-localhost origins"
                    )
        return self

    def require_database_url(self) -> str:
        """Return runtime DATABASE_URL or raise ConfigurationError if unset."""
        if self.DATABASE_URL is None:
            raise ConfigurationError(
                "DATABASE_URL is not configured. Set DATABASE_URL in backend/.env or environment."
            )
        return self.DATABASE_URL.get_secret_value()

    def require_migration_database_url(self) -> str:
        """Return direct Neon/PostgreSQL URL for migrations, falling back to DATABASE_URL."""
        if self.DIRECT_DATABASE_URL is not None:
            return self.DIRECT_DATABASE_URL.get_secret_value()
        return self.require_database_url()

    def require_neon_auth_config(self) -> tuple[str, str]:
        """Return (Neon Auth JWKS URL, issuer) or raise if unset."""
        missing: list[str] = []
        if self.NEON_AUTH_JWKS_URL is None:
            missing.append("NEON_AUTH_JWKS_URL")
        if self.NEON_AUTH_BASE_URL is None:
            missing.append("NEON_AUTH_BASE_URL")
        if missing or self.NEON_AUTH_JWKS_URL is None or self.NEON_AUTH_BASE_URL is None:
            missing_list = ", ".join(missing)
            raise ConfigurationError(
                f"Neon Managed Auth JWT verification is not configured; missing: {missing_list}"
            )
        return self.NEON_AUTH_JWKS_URL, self.NEON_AUTH_BASE_URL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached Settings loader for application and CLI entrypoints."""
    return Settings()
