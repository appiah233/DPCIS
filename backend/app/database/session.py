from collections.abc import Iterator
from threading import Lock
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings

_engine_lock = Lock()
_engines: dict[str, Engine] = {}
_session_factories: dict[str, sessionmaker[Session]] = {}


def normalize_postgres_url(raw_url: str) -> URL:
    """Normalize PostgreSQL URLs to use psycopg v3 without exposing masked passwords."""
    parsed = make_url(raw_url)
    if parsed.drivername in {"postgres", "postgresql"}:
        return parsed.set(drivername="postgresql+psycopg")
    return parsed


def _postgres_connect_args(normalized_url: URL) -> dict[str, Any]:
    """Build psycopg3 connection arguments, disabling prepared statements on Neon poolers."""
    connect_args: dict[str, Any] = {"connect_timeout": 10}
    if normalized_url.host and "-pooler." in normalized_url.host:
        connect_args["prepare_threshold"] = None
    return connect_args


def _build_engine(normalized_url: URL, *, enable_sqlite_fks: bool = False) -> Engine:
    if normalized_url.get_backend_name() == "sqlite":
        engine_kwargs: dict[str, Any] = {
            "connect_args": {"check_same_thread": False},
            "future": True,
        }
        if normalized_url.database in {None, "", ":memory:"}:
            engine_kwargs["poolclass"] = StaticPool
        engine = create_engine(normalized_url, **engine_kwargs)
        if enable_sqlite_fks:

            @event.listens_for(engine, "connect")
            def _enable_sqlite_foreign_keys(
                dbapi_connection: Any,
                _connection_record: Any,
            ) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        return engine

    return create_engine(
        normalized_url,
        pool_pre_ping=True,
        pool_recycle=270,
        pool_size=5,
        max_overflow=5,
        connect_args=_postgres_connect_args(normalized_url),
        future=True,
    )


def _resolve_engine_key_and_url(settings: Settings | None) -> tuple[str, URL, bool]:
    resolved = settings or get_settings()
    raw_url = resolved.require_database_url()
    normalized = normalize_postgres_url(raw_url)
    enable_sqlite_fks = resolved.APP_ENV == "test"
    cache_key = f"{resolved.APP_ENV}:{normalized.render_as_string(hide_password=False)}"
    return cache_key, normalized, enable_sqlite_fks


def get_engine(settings: Settings | None = None) -> Engine:
    """Lazily construct and return a pooled SQLAlchemy Engine for runtime queries."""
    cache_key, normalized, enable_sqlite_fks = _resolve_engine_key_and_url(settings)

    with _engine_lock:
        engine = _engines.get(cache_key)
        if engine is None:
            engine = _build_engine(normalized, enable_sqlite_fks=enable_sqlite_fks)
            _engines[cache_key] = engine
        return engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Lazily construct and return a sessionmaker bound to the configured Engine."""
    cache_key, normalized, enable_sqlite_fks = _resolve_engine_key_and_url(settings)

    with _engine_lock:
        factory = _session_factories.get(cache_key)
        if factory is None:
            engine = _engines.get(cache_key)
            if engine is None:
                engine = _build_engine(normalized, enable_sqlite_fks=enable_sqlite_fks)
                _engines[cache_key] = engine
            factory = sessionmaker(
                bind=engine,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
            )
            _session_factories[cache_key] = factory
        return factory


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a synchronous database Session for `def` route handlers."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Dispose all cached SQLAlchemy engines during graceful application shutdown."""
    with _engine_lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()
        _session_factories.clear()

