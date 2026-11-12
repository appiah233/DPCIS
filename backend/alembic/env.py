import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.attempts import models as _attempts_models  # noqa: F401
from app.config import get_settings
from app.database import Base, normalize_postgres_url
from app.exams import models as _exams_models  # noqa: F401
from app.users import models as _users_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")
target_metadata = Base.metadata


def include_object(
    obj: object,
    _name: str | None,
    _type: str,
    _reflected: bool,
    _compare_to: object,
) -> bool:
    """Exclude Neon-managed auth tables and child objects from Alembic operations."""
    if getattr(obj, "schema", None) == "neon_auth":
        return False
    table = getattr(obj, "table", None)
    if table is not None and getattr(table, "schema", None) == "neon_auth":
        return False
    return True


def _resolve_migration_url():
    settings = get_settings()
    raw_url = settings.require_migration_database_url()
    normalized = normalize_postgres_url(raw_url)
    if normalized.host and "-pooler." in normalized.host and ".neon.tech" in normalized.host:
        logger.warning(
            "Running Alembic against a Neon '-pooler' endpoint; "
            "configure DIRECT_DATABASE_URL for direct non-pooled migrations."
        )
    return normalized


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without opening a live database socket."""
    migration_url = _resolve_migration_url()
    context.configure(
        url=migration_url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using NullPool and direct URL resolution."""
    migration_url = _resolve_migration_url()
    connect_args = (
        {"prepare_threshold": None}
        if migration_url.host and "-pooler." in migration_url.host
        else {}
    )
    connectable = create_engine(
        migration_url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

