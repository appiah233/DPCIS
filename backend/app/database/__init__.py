"""Database foundation package (SQLAlchemy 2.x DeclarativeBase and lazy session setup).

Importing all domain models here registers every table with ``Base.metadata`` so
Alembic autogeneration and ``create_all`` see the complete application schema.
Neon Managed Auth tables are intentionally not registered here.
"""

from app.database.base import POSTGRES_NAMING_CONVENTION, Base
from app.database.session import (
    dispose_engine,
    get_db,
    get_engine,
    get_session_factory,
    normalize_postgres_url,
)

# isort: split
# Import domain models after Base initializes so SQLAlchemy registers every table.
from app.attempts import models as _attempts_models  # noqa: F401
from app.exams import models as _exams_models  # noqa: F401
from app.users import models as _users_models  # noqa: F401

__all__ = [
    "Base",
    "POSTGRES_NAMING_CONVENTION",
    "dispose_engine",
    "get_db",
    "get_engine",
    "get_session_factory",
    "normalize_postgres_url",
]

