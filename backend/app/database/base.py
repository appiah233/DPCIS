from collections.abc import Callable
from datetime import datetime

from sqlalchemy import Constraint, DateTime, MetaData, Table, exc
from sqlalchemy.orm import DeclarativeBase


def _format_check_constraint_name(constraint: Constraint, table: Table) -> str:
    """Format CHECK constraint names without double-prefixing ``ck_<table>_``."""
    raw_name = constraint.name
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise exc.InvalidRequestError(
            "Naming convention including %(constraint_name)s token requires that "
            "constraint is explicitly named."
        )
    prefix = f"ck_{table.name}_"
    if raw_name.startswith(prefix):
        return raw_name
    return f"{prefix}{raw_name}"


POSTGRES_NAMING_CONVENTION: dict[str, str | Callable[[Constraint, Table], str]] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck_constraint_name": _format_check_constraint_name,
    "ck": "%(ck_constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared SQLAlchemy 2.x DeclarativeBase for all Examination Hub entities."""

    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }

