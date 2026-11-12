"""Application users persistence and identity-resolution service.

Maps Neon Managed Better Auth subjects (JWT ``sub``) to local PostgreSQL
``application_users`` records. Application roles are strictly owned by the
database and are never derived from client tokens or request payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Uuid,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

DEFAULT_STUDENT_ROLE = "STUDENT"

# Isolated metadata fallback used only if app.users.models is not yet loaded.
# Never attached to Base.metadata so ORM table registration cannot collide.
_FALLBACK_METADATA = MetaData()
_FALLBACK_APPLICATION_USERS_TABLE = Table(
    "application_users",
    _FALLBACK_METADATA,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("auth_subject", String(255), nullable=False, unique=True),
    Column("email", String(320), nullable=True),
    Column("display_name", String(255), nullable=True),
    Column("role", String(16), nullable=False, server_default=DEFAULT_STUDENT_ROLE),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


@dataclass(frozen=True)
class ApplicationUserRecord:
    """Resolved ``application_users`` record."""

    id: UUID
    auth_subject: str
    email: str | None
    display_name: str | None
    role: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _get_users_table() -> Table:
    try:
        from app.users.models import ApplicationUser
    except ImportError:
        return _FALLBACK_APPLICATION_USERS_TABLE
    return ApplicationUser.__table__


def _normalize_subject(auth_subject: str) -> str:
    if not isinstance(auth_subject, str) or not auth_subject.strip():
        raise ValueError("auth_subject must be a non-empty string")
    return auth_subject.strip()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _coerce_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _build_new_id(table: Table) -> UUID | str:
    id_type = table.c.id.type
    if isinstance(id_type, Uuid) and id_type.as_uuid:
        return uuid4()
    return str(uuid4())


def _row_to_record(row: Any) -> ApplicationUserRecord:
    return ApplicationUserRecord(
        id=_coerce_uuid(row.id),
        auth_subject=row.auth_subject,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        created_at=getattr(row, "created_at", None),
        updated_at=getattr(row, "updated_at", None),
    )


def get_application_user_by_subject(
    db: Session,
    auth_subject: str,
) -> ApplicationUserRecord | None:
    """Return the local ``application_users`` record for ``auth_subject``, if present."""
    clean_subject = _normalize_subject(auth_subject)
    table = _get_users_table()
    stmt = select(
        table.c.id,
        table.c.auth_subject,
        table.c.email,
        table.c.display_name,
        table.c.role,
        table.c.created_at,
        table.c.updated_at,
    ).where(table.c.auth_subject == clean_subject)
    row = db.execute(stmt).one_or_none()
    if row is None:
        return None
    return _row_to_record(row)


def upsert_application_user(
    db: Session,
    *,
    auth_subject: str,
    email: str | None,
    display_name: str | None,
    commit: bool = True,
) -> ApplicationUserRecord:
    """Idempotently provision or refresh an ``application_users`` row by ``auth_subject``.

    New accounts are always inserted with ``role='STUDENT'``. Existing accounts
    preserve their database-authoritative ``role`` and keep existing non-null
    ``email`` / ``display_name`` values when incoming claims are ``None``.
    """
    clean_subject = _normalize_subject(auth_subject)
    clean_email = _normalize_optional_text(email)
    clean_name = _normalize_optional_text(display_name)
    table = _get_users_table()
    now = datetime.now(UTC)

    bind = db.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""

    if dialect_name in {"postgresql", "sqlite"}:
        insert_fn = pg_insert if dialect_name == "postgresql" else sqlite_insert
        stmt = insert_fn(table).values(
            id=_build_new_id(table),
            auth_subject=clean_subject,
            email=clean_email,
            display_name=clean_name,
            role=DEFAULT_STUDENT_ROLE,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.auth_subject],
            set_={
                "email": func.coalesce(stmt.excluded.email, table.c.email),
                "display_name": func.coalesce(stmt.excluded.display_name, table.c.display_name),
                "updated_at": now,
            },
        ).returning(
            table.c.id,
            table.c.auth_subject,
            table.c.email,
            table.c.display_name,
            table.c.role,
            table.c.created_at,
            table.c.updated_at,
        )
        row = db.execute(stmt).one()
        if commit:
            db.commit()
        else:
            db.flush()
        return _row_to_record(row)

    # Generic fallback for non-PostgreSQL/SQLite dialects.
    existing = get_application_user_by_subject(db, clean_subject)
    if existing is None:
        try:
            db.execute(
                sa.insert(table).values(
                    id=_build_new_id(table),
                    auth_subject=clean_subject,
                    email=clean_email,
                    display_name=clean_name,
                    role=DEFAULT_STUDENT_ROLE,
                    created_at=now,
                    updated_at=now,
                )
            )
            if commit:
                db.commit()
            else:
                db.flush()
            created = get_application_user_by_subject(db, clean_subject)
            assert created is not None  # noqa: S101
            return created
        except IntegrityError:
            db.rollback()
            existing = get_application_user_by_subject(db, clean_subject)
            if existing is None:
                raise

    db.execute(
        update(table)
        .where(table.c.auth_subject == clean_subject)
        .values(
            email=clean_email if clean_email is not None else existing.email,
            display_name=clean_name if clean_name is not None else existing.display_name,
            updated_at=now,
        )
    )
    if commit:
        db.commit()
    else:
        db.flush()
    refreshed = get_application_user_by_subject(db, clean_subject)
    assert refreshed is not None  # noqa: S101
    return refreshed
