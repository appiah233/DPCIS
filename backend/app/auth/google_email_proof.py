"""Application access gate for Google users' independent email proof.

Google verifies its own account email, but a separate OTP proves control of the
mailbox for Examination Hub. Only the backend may record this proof. The OTP is
validated and consumed by Neon Managed Auth, and is never stored or logged here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException
from sqlalchemy import Column, DateTime, MetaData, String, Table, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthIdentity
from app.config import Settings

_metadata = MetaData()
proofs = Table(
    "application_google_email_proofs",
    _metadata,
    Column("auth_subject", String(255), primary_key=True),
    Column("email", String(320), nullable=False),
    Column("confirmed_at", DateTime(timezone=True), nullable=False),
)


def google_email_needs_proof(db: Session, identity: AuthIdentity) -> bool:
    if db.get_bind().dialect.name != "postgresql":
        return False  # Isolated SQLite tests do not have Neon's managed schema.
    if not identity.email:
        raise HTTPException(403, "Verified email required")
    google_account = db.execute(
        text(
            'SELECT 1 FROM neon_auth.account WHERE "userId" = :subject '
            'AND "providerId" = :provider LIMIT 1'
        ),
        {"subject": identity.subject, "provider": "google"},
    ).scalar_one_or_none()
    if not google_account:
        return False
    confirmed = db.execute(
        select(proofs.c.email).where(proofs.c.auth_subject == identity.subject)
    ).scalar_one_or_none()
    return confirmed is None or confirmed.casefold() != identity.email.casefold()


def require_google_email_proof(db: Session, identity: AuthIdentity) -> None:
    if google_email_needs_proof(db, identity):
        raise HTTPException(403, "GOOGLE_EMAIL_PROOF_REQUIRED")


def confirm_google_email_and_password(
    db: Session,
    identity: AuthIdentity,
    settings: Settings,
    otp: str,
    password: str,
    *,
    origin: str | None = None,
) -> None:
    if origin is None or origin not in settings.CORS_ORIGINS:
        raise HTTPException(403, "Untrusted application origin")
    if not google_email_needs_proof(db, identity):
        raise HTTPException(409, "Google email proof is not required")
    if not settings.NEON_AUTH_BASE_URL:
        raise HTTPException(503, "Authentication provider is not configured")
    if not settings.NEON_AUTH_BASE_URL.startswith("https://"):
        raise HTTPException(503, "Authentication provider URL must use HTTPS")
    payload = json.dumps({"email": identity.email, "otp": otp, "password": password}).encode()
    request = Request(  # noqa: S310 - validated HTTPS Neon Auth origin above
        settings.NEON_AUTH_BASE_URL.rstrip("/") + "/email-otp/reset-password",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": origin,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:  # noqa: S310
            if response.status >= 300:
                raise HTTPException(400, "Verification code was not accepted")
            try:
                confirmed = json.loads(response.read(8192))
            except (ValueError, UnicodeDecodeError) as exc:
                raise HTTPException(
                    502, "Authentication provider returned an invalid response"
                ) from exc
            if not isinstance(confirmed, dict) or confirmed.get("success") is not True:
                raise HTTPException(
                    502, "Authentication provider did not confirm password creation"
                )
    except HTTPError as exc:
        try:
            rejected = json.loads(exc.read(8192))
        except (ValueError, UnicodeDecodeError):
            rejected = {}
        code = rejected.get("code") if isinstance(rejected, dict) else None
        if not isinstance(code, str):
            code = None
        if exc.code == 429 or code in ("TOO_MANY_REQUESTS", "TOO_MANY_ATTEMPTS"):
            raise HTTPException(
                429, "Too many attempts. Wait before requesting a new code."
            ) from exc
        if exc.code >= 500:
            raise HTTPException(503, "Authentication provider is temporarily unavailable") from exc
        messages = {
            "OTP_EXPIRED": "Your verification code has expired. Request a new code.",
            "INVALID_OTP": (
                "The verification code is incorrect. Use the most recent code sent to you."
            ),
            "PASSWORD_TOO_SHORT": "Please use a password with at least 8 characters.",
            "PASSWORD_TOO_LONG": "Please use a password with no more than 128 characters.",
        }
        if code in ("MISSING_ORIGIN", "INVALID_ORIGIN"):
            raise HTTPException(
                502, "Authentication configuration needs attention. Please try again later."
            ) from exc
        raise HTTPException(
            400, messages.get(code, "Verification code or password was not accepted")
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(503, "Authentication provider is temporarily unavailable") from exc
    now = datetime.now(UTC)
    existing = db.execute(
        select(proofs.c.auth_subject).where(proofs.c.auth_subject == identity.subject)
    ).scalar_one_or_none()
    if existing:
        db.execute(
            proofs.update()
            .where(proofs.c.auth_subject == identity.subject)
            .values(email=identity.email, confirmed_at=now)
        )
    else:
        db.execute(
            proofs.insert().values(
                auth_subject=identity.subject, email=identity.email, confirmed_at=now
            )
        )
    db.commit()
