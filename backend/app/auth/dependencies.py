from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.config import ConfigurationError, Settings, get_settings
from app.database.session import get_db
from app.users.service import (
    get_application_user_by_subject,
    get_managed_auth_role,
    upsert_application_user,
)

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_ADMIN = "ADMIN"
ROLE_STUDENT = "STUDENT"


@dataclass(frozen=True)
class AuthIdentity:
    subject: str
    email: str | None
    name: str | None
    role: str | None = None
    user_id: UUID | None = None


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, timeout=5)


def _clean_optional_claim(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _managed_auth_issuer(base_url: str) -> str:
    """Return the issuer used by Neon Managed Auth JWTs.

    Neon exposes its Auth API below a branch-specific path such as
    ``/neondb/auth``, while JWT ``iss`` is the URL origin. Configuration
    validation already guarantees an absolute HTTPS URL.
    """
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def require_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthIdentity:
    """Verify the Neon Managed Auth EdDSA Bearer JWT and return the identity.

    Application role and internal ``user_id`` are intentionally NOT loaded here.
    Authorization is handled by ``require_student`` / ``require_admin`` using the
    authoritative record in PostgreSQL ``application_users``.
    """
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        jwks_url, issuer = settings.require_neon_auth_config()
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(credentials.credentials)
        decode_options: dict[str, Any] = {
            "require": ["exp", "sub"],
            "verify_aud": bool(settings.NEON_AUTH_AUDIENCE),
        }
        decode_kwargs: dict[str, Any] = {
            "algorithms": ["EdDSA"],
            "issuer": _managed_auth_issuer(issuer),
            "options": decode_options,
        }
        if settings.NEON_AUTH_AUDIENCE:
            decode_kwargs["audience"] = settings.NEON_AUTH_AUDIENCE
        claims = jwt.decode(credentials.credentials, signing_key.key, **decode_kwargs)
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is not configured",
        ) from exc
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is temporarily unavailable",
        ) from exc
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (jwt.PyJWTError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthIdentity(
        subject=subject.strip(),
        email=_clean_optional_claim(claims.get("email")),
        name=_clean_optional_claim(claims.get("name")),
        role=None,
        user_id=None,
    )


def _load_application_user(db: Session, auth_subject: str) -> tuple[UUID, str] | None:
    """Load the application user ID and mirrored role from PostgreSQL."""
    user = get_application_user_by_subject(db, auth_subject)
    if user is None:
        return None
    return user.id, user.role


def _load_application_role(db: Session, auth_subject: str) -> str | None:
    """Thin wrapper returning only the authoritative ``application_users.role``."""
    loaded = _load_application_user(db, auth_subject)
    if loaded is None:
        return None
    return loaded[1]


def _current_managed_role(db: Session, auth_subject: str) -> str | None:
    role = get_managed_auth_role(db, auth_subject)
    if role is None and db.get_bind().dialect.name == "postgresql":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managed authentication role unavailable",
        )
    return role


def require_student(
    identity: AuthIdentity = Depends(require_identity),
    db: Session = Depends(get_db),
) -> AuthIdentity:
    """Require an authenticated identity whose application role is STUDENT.

    The verified JWT subject resolves to Neon's current role. PostgreSQL
    application users mirror it before the student permission check.
    """
    managed_role = _current_managed_role(db, identity.subject)
    provisioned = upsert_application_user(
        db,
        auth_subject=identity.subject,
        email=identity.email,
        display_name=identity.name,
        managed_role=managed_role,
    )
    user_id, role = provisioned.id, provisioned.role

    if role != ROLE_STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student role required",
        )
    return AuthIdentity(
        subject=identity.subject,
        email=identity.email,
        name=identity.name,
        role=role,
        user_id=user_id,
    )


def require_admin(
    identity: AuthIdentity = Depends(require_identity),
    db: Session = Depends(get_db),
) -> AuthIdentity:
    """Require an authenticated identity whose application role is ADMIN.

    PostgreSQL reads Neon's current role before the admin permission check.
    An unknown managed role fails closed.
    """
    managed_role = _current_managed_role(db, identity.subject)
    if managed_role is not None:
        provisioned = upsert_application_user(
            db,
            auth_subject=identity.subject,
            email=identity.email,
            display_name=identity.name,
            managed_role=managed_role,
        )
        loaded = provisioned.id, provisioned.role
    else:
        loaded = _load_application_user(db, identity.subject)
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Application identity not found. Sign in to establish your application role.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id, role = loaded
    if role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return AuthIdentity(
        subject=identity.subject,
        email=identity.email,
        name=identity.name,
        role=role,
        user_id=user_id,
    )
