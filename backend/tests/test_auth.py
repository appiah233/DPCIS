import time
from collections.abc import Iterator
from types import SimpleNamespace
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import (
    ROLE_ADMIN,
    ROLE_STUDENT,
    AuthIdentity,
    require_admin,
    require_identity,
    require_student,
)
from app.auth import dependencies as auth_dependencies
from app.config import Settings
from app.database.session import get_db
from app.main import create_app
from app.users.service import (
    _get_users_table,
    get_application_user_by_subject,
    upsert_application_user,
)


def _auth_enabled_settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        CORS_ORIGINS=["http://localhost:5173"],
        NEON_AUTH_BASE_URL="https://auth.example.com",
        NEON_AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
        NEON_AUTH_AUDIENCE="examination-hub",
    )


def _make_eddsa_token(
    private_key: Ed25519PrivateKey,
    *,
    sub: str | None = "neon_user_abc123",
    iss: str | None = "https://auth.example.com",
    aud: str | None = "examination-hub",
    exp_offset: int | None = 300,
    nbf_offset: int | None = None,
    extra_claims: dict[str, object] | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, object] = {}
    if sub is not None:
        payload["sub"] = sub
    if iss is not None:
        payload["iss"] = iss
    if aud is not None:
        payload["aud"] = aud
    if exp_offset is not None:
        payload["exp"] = now + exp_offset
    if nbf_offset is not None:
        payload["nbf"] = now + nbf_offset
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, private_key, algorithm="EdDSA")


def _sqlite_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    _get_users_table().create(engine, checkfirst=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _build_auth_test_app(
    monkeypatch: pytest.MonkeyPatch,
    public_key: object,
) -> tuple[TestClient, sessionmaker[Session]]:
    monkeypatch.setattr(
        auth_dependencies,
        "_jwks_client",
        lambda _url: SimpleNamespace(
            get_signing_key_from_jwt=lambda _tok: SimpleNamespace(key=public_key)
        ),
    )

    session_factory = _sqlite_session_factory()

    def _override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app(settings=_auth_enabled_settings())
    app.dependency_overrides[get_db] = _override_get_db

    probe_router = APIRouter()

    @probe_router.get("/__test/student-only")
    def student_probe(identity: AuthIdentity = Depends(require_student)) -> dict[str, str | None]:
        return {
            "user_id": str(identity.user_id) if identity.user_id is not None else None,
            "subject": identity.subject,
            "role": identity.role,
        }

    @probe_router.get("/__test/admin-only")
    def admin_probe(identity: AuthIdentity = Depends(require_admin)) -> dict[str, str | None]:
        return {
            "user_id": str(identity.user_id) if identity.user_id is not None else None,
            "subject": identity.subject,
            "role": identity.role,
        }

    app.include_router(probe_router)
    client = TestClient(app, raise_server_exceptions=False)
    return client, session_factory


def test_auth_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.parametrize(
    "auth_header",
    [
        "Basic dXNlcjpwYXNz",
        "Bearer ",
        "Bearer",
    ],
)
def test_auth_me_rejects_non_bearer_or_empty_token(
    client: TestClient,
    auth_header: str,
) -> None:
    response = client.get("/auth/me", headers={"Authorization": auth_header})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_auth_me_returns_503_when_neon_auth_not_configured(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer any-token"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication provider is not configured"}


def test_auth_me_returns_503_when_jwks_endpoint_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_jwks_connection_error(_tok: str) -> object:
        raise jwt.PyJWKClientConnectionError("Connection refused")

    monkeypatch.setattr(
        auth_dependencies,
        "_jwks_client",
        lambda _url: SimpleNamespace(get_signing_key_from_jwt=_raise_jwks_connection_error),
    )

    app = create_app(settings=_auth_enabled_settings())
    session_factory = _sqlite_session_factory()
    app.dependency_overrides[get_db] = lambda: session_factory()

    with TestClient(app) as client:
        response = client.get("/auth/me", headers={"Authorization": "Bearer some.jwt.token"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication provider is temporarily unavailable"}


def test_auth_me_rejects_invalid_eddsa_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    wrong_key = Ed25519PrivateKey.generate()
    token = _make_eddsa_token(wrong_key, sub="user-123")

    test_client, session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with test_client as client:
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"detail": "Invalid authentication token"}
    with session_factory() as db:
        assert get_application_user_by_subject(db, "user-123") is None


def test_auth_me_distinguishes_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _make_eddsa_token(private_key, exp_offset=-120)

    test_client, _session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with test_client as client:
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"detail": "Authentication token expired"}


@pytest.mark.parametrize(
    "token_overrides",
    [
        {"exp_offset": -120},
        {"nbf_offset": 120},
        {"exp_offset": None},
        {"iss": "https://evil.example.com"},
        {"aud": "other-service"},
        {"sub": None},
        {"sub": "   "},
    ],
)
def test_auth_me_rejects_expired_immature_unbounded_or_invalid_claims(
    monkeypatch: pytest.MonkeyPatch,
    token_overrides: dict[str, object],
) -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _make_eddsa_token(private_key, **token_overrides)  # type: ignore[arg-type]

    test_client, _session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with test_client as client:
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_auth_me_rejects_hs256_and_alg_none_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    now = int(time.time())
    hs256_token = jwt.encode(
        {
            "sub": "attacker-1",
            "iss": "https://auth.example.com",
            "aud": "examination-hub",
            "exp": now + 300,
        },
        "shared-secret-not-eddsa",
        algorithm="HS256",
    )
    none_token = jwt.encode(
        {
            "sub": "attacker-2",
            "iss": "https://auth.example.com",
            "aud": "examination-hub",
            "exp": now + 300,
        },
        key="",
        algorithm="none",
    )

    test_client, _session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with test_client as client:
        for bad_token in (hs256_token, none_token):
            response = client.get("/auth/me", headers={"Authorization": f"Bearer {bad_token}"})
            assert response.status_code == 401
            assert response.headers.get("www-authenticate") == "Bearer"


def test_require_identity_uses_auth_origin_as_managed_neon_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Managed Neon tokens use the Auth URL origin even when the API has a path."""
    private_key = Ed25519PrivateKey.generate()
    token = _make_eddsa_token(
        private_key,
        sub="neon_path_issuer_user",
        iss="https://auth.example.com",
        aud=None,
    )
    monkeypatch.setattr(
        auth_dependencies,
        "_jwks_client",
        lambda _url: SimpleNamespace(
            get_signing_key_from_jwt=lambda _tok: SimpleNamespace(key=private_key.public_key())
        ),
    )
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        CORS_ORIGINS=["http://localhost:5173"],
        NEON_AUTH_BASE_URL="https://auth.example.com/neondb/auth",
        NEON_AUTH_JWKS_URL="https://auth.example.com/neondb/auth/.well-known/jwks.json",
        NEON_AUTH_AUDIENCE=None,
    )

    identity = require_identity(
        credentials=SimpleNamespace(scheme="Bearer", credentials=token),  # type: ignore[arg-type]
        settings=settings,
    )

    assert identity.subject == "neon_path_issuer_user"


def test_auth_me_verifies_eddsa_token_provisions_student_and_ignores_jwt_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _make_eddsa_token(
        private_key,
        sub="neon_user_abc123",
        extra_claims={
            "email": "student@example.edu",
            "name": "Ada Student",
            "role": "ADMIN",  # Client claim must not control database role
        },
    )

    test_client, session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with test_client as client:
        first = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        second = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert first.status_code == 200
    payload = first.json()
    parsed_user_id = UUID(payload["user_id"])
    assert payload == {
        "user_id": str(parsed_user_id),
        "auth_subject": "neon_user_abc123",
        "email": "student@example.edu",
        "display_name": "Ada Student",
        "role": ROLE_STUDENT,
    }
    assert second.status_code == 200
    assert second.json()["user_id"] == payload["user_id"]

    with session_factory() as db:
        stored = get_application_user_by_subject(db, "neon_user_abc123")
        assert stored is not None
        assert stored.id == parsed_user_id
        assert stored.role == ROLE_STUDENT


def test_auth_me_coalesces_null_metadata_and_preserves_promoted_admin_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    initial_token = _make_eddsa_token(
        private_key,
        sub="neon_admin_001",
        extra_claims={"email": "admin@example.edu", "name": "Grace Admin"},
    )
    sparse_token = _make_eddsa_token(
        private_key,
        sub="neon_admin_001",
        extra_claims={"role": "STUDENT"},  # Missing email/name, conflicting JWT role claim
    )
    updated_email_token = _make_eddsa_token(
        private_key,
        sub="neon_admin_001",
        extra_claims={"email": "grace.hopper@example.edu"},
    )

    test_client, session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with test_client as client:
        created = client.get("/auth/me", headers={"Authorization": f"Bearer {initial_token}"})
        assert created.status_code == 200
        original_id = created.json()["user_id"]

        with session_factory() as db:
            db.execute(
                text(
                    "UPDATE application_users SET role = :role WHERE auth_subject = :auth_subject"
                ),
                {"role": ROLE_ADMIN, "auth_subject": "neon_admin_001"},
            )
            db.commit()

        after_sparse = client.get("/auth/me", headers={"Authorization": f"Bearer {sparse_token}"})
        assert after_sparse.status_code == 200
        assert after_sparse.json() == {
            "user_id": original_id,
            "auth_subject": "neon_admin_001",
            "email": "admin@example.edu",
            "display_name": "Grace Admin",
            "role": ROLE_ADMIN,
        }

        after_update = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {updated_email_token}"},
        )
        assert after_update.status_code == 200
        assert after_update.json() == {
            "user_id": original_id,
            "auth_subject": "neon_admin_001",
            "email": "grace.hopper@example.edu",
            "display_name": "Grace Admin",
            "role": ROLE_ADMIN,
        }


def test_require_student_auto_provisions_student_and_populates_user_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    # Student has not called /auth/me yet and sends a malicious role="ADMIN" claim.
    token = _make_eddsa_token(
        private_key,
        sub="neon_direct_student",
        extra_claims={
            "email": "direct@example.edu",
            "name": "Direct Student",
            "role": "ADMIN",
        },
    )

    test_client, session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with test_client as client:
        response = client.get(
            "/__test/student-only",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    resolved_uuid = UUID(payload["user_id"])
    assert payload == {
        "user_id": str(resolved_uuid),
        "subject": "neon_direct_student",
        "role": ROLE_STUDENT,
    }

    with session_factory() as db:
        stored = get_application_user_by_subject(db, "neon_direct_student")
        assert stored is not None
        assert stored.id == resolved_uuid
        assert stored.role == ROLE_STUDENT


def test_require_student_rejects_unauthenticated_and_admin_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    admin_token = _make_eddsa_token(private_key, sub="neon_admin_user")

    test_client, session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with session_factory() as db:
        upsert_application_user(
            db,
            auth_subject="neon_admin_user",
            email="boss@example.edu",
            display_name="Exam Admin",
        )
        db.execute(
            text("UPDATE application_users SET role = :role WHERE auth_subject = :auth_subject"),
            {"role": ROLE_ADMIN, "auth_subject": "neon_admin_user"},
        )
        db.commit()

    with test_client as client:
        unauth = client.get("/__test/student-only")
        assert unauth.status_code == 401

        as_admin = client.get(
            "/__test/student-only",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert as_admin.status_code == 403
        assert as_admin.json() == {"detail": "Student role required"}


def test_require_admin_fails_closed_for_unprovisioned_and_student_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    unprovisioned_token = _make_eddsa_token(
        private_key,
        sub="neon_unprovisioned_probe",
        extra_claims={"role": "ADMIN"},
    )
    student_token = _make_eddsa_token(
        private_key,
        sub="neon_regular_student",
        extra_claims={"role": "ADMIN"},
    )

    test_client, session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with session_factory() as db:
        upsert_application_user(
            db,
            auth_subject="neon_regular_student",
            email="student@example.edu",
            display_name="Regular Student",
        )

    with test_client as client:
        unauth = client.get("/__test/admin-only")
        assert unauth.status_code == 401

        unprovisioned = client.get(
            "/__test/admin-only",
            headers={"Authorization": f"Bearer {unprovisioned_token}"},
        )
        assert unprovisioned.status_code == 401
        assert unprovisioned.headers.get("www-authenticate") == "Bearer"

        as_student = client.get(
            "/__test/admin-only",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert as_student.status_code == 403
        assert as_student.json() == {"detail": "Admin role required"}

    with session_factory() as db:
        assert get_application_user_by_subject(db, "neon_unprovisioned_probe") is None


def test_require_admin_succeeds_for_db_admin_and_populates_user_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    admin_token = _make_eddsa_token(private_key, sub="neon_db_admin")

    test_client, session_factory = _build_auth_test_app(monkeypatch, private_key.public_key())
    with session_factory() as db:
        created = upsert_application_user(
            db,
            auth_subject="neon_db_admin",
            email="admin@example.edu",
            display_name="Admin User",
        )
        db.execute(
            text("UPDATE application_users SET role = :role WHERE auth_subject = :auth_subject"),
            {"role": ROLE_ADMIN, "auth_subject": "neon_db_admin"},
        )
        db.commit()

    with test_client as client:
        response = client.get(
            "/__test/admin-only",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(created.id),
        "subject": "neon_db_admin",
        "role": ROLE_ADMIN,
    }


def test_users_service_rejects_empty_auth_subject() -> None:
    session_factory = _sqlite_session_factory()
    with session_factory() as db:
        with pytest.raises(ValueError, match="auth_subject"):
            get_application_user_by_subject(db, "   ")
        with pytest.raises(ValueError, match="auth_subject"):
            upsert_application_user(db, auth_subject="", email=None, display_name=None)


def test_require_identity_unit_populates_none_user_id_and_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _make_eddsa_token(
        private_key,
        sub="unit-sub",
        extra_claims={"email": "  unit@example.edu ", "name": "   ", "role": "ADMIN"},
    )
    monkeypatch.setattr(
        auth_dependencies,
        "_jwks_client",
        lambda _url: SimpleNamespace(
            get_signing_key_from_jwt=lambda _tok: SimpleNamespace(key=private_key.public_key())
        ),
    )

    identity = require_identity(
        credentials=SimpleNamespace(scheme="Bearer", credentials=token),  # type: ignore[arg-type]
        settings=_auth_enabled_settings(),
    )
    assert identity == AuthIdentity(
        subject="unit-sub",
        email="unit@example.edu",
        name=None,
        role=None,
        user_id=None,
    )
