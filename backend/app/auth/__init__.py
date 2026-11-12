"""Neon Managed Better Auth verification boundary.

Authentication is delegated to Neon Managed Better Auth (EdDSA JWTs). Application roles
are stored separately in ``application_users`` keyed by ``auth_subject`` and are never
inferred from an email address or client token claims.
"""

from app.auth.dependencies import (
    ROLE_ADMIN,
    ROLE_STUDENT,
    AuthIdentity,
    require_admin,
    require_identity,
    require_student,
)

__all__ = [
    "AuthIdentity",
    "ROLE_ADMIN",
    "ROLE_STUDENT",
    "require_admin",
    "require_identity",
    "require_student",
]
