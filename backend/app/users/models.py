"""Users domain SQLAlchemy models.

Mirrors ``0001_application_users`` cleanly. Stores application-owned identity
and authoritative role keyed by Neon Managed Better Auth ``auth_subject``
(JWT ``sub``). Neon-managed ``neon_auth.*`` tables are never mapped here.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from app.database.base import Base


class ApplicationUser(Base):
    __tablename__ = "application_users"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    auth_subject: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="STUDENT",
        server_default=sa.text("'STUDENT'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('STUDENT', 'ADMIN')",
            name=conv("ck_application_users_role"),
        ),
    )
