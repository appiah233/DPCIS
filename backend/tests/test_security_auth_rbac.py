"""Adversarial authentication and role-based access control (RBAC) tests.

Covers matrix cases SEC-AUTH-01..04 and SEC-RBAC-01..04 against the full
integrated FastAPI application (``create_app()``) with real Ed25519 JWTs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.database  # noqa: F401
from app.auth import ROLE_ADMIN, ROLE_STUDENT
from app.auth import dependencies as auth_dependencies
from app.config import Settings
from app.database import Base
from app.database.session import get_db
from app.main import create_app
from app.users.models import ApplicationUser


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _auth_settings(*, audience: str | None = "examination-hub") -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        CORS_ORIGINS=["http://localhost:5173"],
        NEON_AUTH_BASE_URL="https://auth.example.com",
        NEON_AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
        NEON_AUTH_AUDIENCE=audience,
    )


def _make_eddsa_token(
    private_key: Ed25519PrivateKey,
    *,
    sub: object = "neon_user_001",
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


@contextmanager
def _build_integrated_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    settings: Settings | None = None,
    public_key: object | None = None,
    jwks_error: Exception | None = None,
) -> Iterator[SimpleNamespace]:
    private_key = Ed25519PrivateKey.generate()
    verifying_key = public_key or private_key.public_key()

    if jwks_error is not None:

        def _failing_key_lookup(_tok: str) -> object:
            raise jwks_error

        monkeypatch.setattr(
            auth_dependencies,
            "_jwks_client",
            lambda _url: SimpleNamespace(get_signing_key_from_jwt=_failing_key_lookup),
        )
    else:
        monkeypatch.setattr(
            auth_dependencies,
            "_jwks_client",
            lambda _url: SimpleNamespace(
                get_signing_key_from_jwt=lambda _tok: SimpleNamespace(key=verifying_key)
            ),
        )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def _override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app(settings=settings or _auth_settings())
    app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield SimpleNamespace(
                client=client,
                app=app,
                private_key=private_key,
                session_factory=session_factory,
            )
    finally:
        engine.dispose()


_DUMMY_EXAM_ID = str(uuid4())
_DUMMY_QUESTION_ID = str(uuid4())
_DUMMY_ATTEMPT_ID = str(uuid4())

ADMIN_ENDPOINTS: list[tuple[str, str, dict[str, object] | None]] = [
    ("POST", "/api/admin/exams", {"title": "Probe", "duration_minutes": 10}),
    ("GET", "/api/admin/exams", None),
    ("POST", "/api/admin/exams/parse-questions", {"raw_text": "1. Q?\nA. x\nB. y\nANSWER: A"}),
    ("GET", f"/api/admin/exams/{_DUMMY_EXAM_ID}", None),
    ("PATCH", f"/api/admin/exams/{_DUMMY_EXAM_ID}", {"title": "Updated"}),
    ("DELETE", f"/api/admin/exams/{_DUMMY_EXAM_ID}", None),
    ("PUT", f"/api/admin/exams/{_DUMMY_EXAM_ID}/questions", []),
    ("POST", f"/api/admin/exams/{_DUMMY_EXAM_ID}/questions", {}),
    ("PUT", f"/api/admin/exams/{_DUMMY_EXAM_ID}/questions/{_DUMMY_QUESTION_ID}", {}),
    ("DELETE", f"/api/admin/exams/{_DUMMY_EXAM_ID}/questions/{_DUMMY_QUESTION_ID}", None),
    ("POST", f"/api/admin/exams/{_DUMMY_EXAM_ID}/publish", None),
    ("POST", f"/api/admin/exams/{_DUMMY_EXAM_ID}/close", None),
    ("GET", f"/api/admin/exams/{_DUMMY_EXAM_ID}/results", None),
    ("GET", f"/api/admin/attempts/{_DUMMY_ATTEMPT_ID}", None),
]

STUDENT_ENDPOINTS: list[tuple[str, str, dict[str, object] | None]] = [
    ("GET", "/api/exams", None),
    ("GET", f"/api/exams/{_DUMMY_EXAM_ID}", None),
    ("POST", f"/api/exams/{_DUMMY_EXAM_ID}/attempts", None),
    ("GET", f"/api/attempts/{_DUMMY_ATTEMPT_ID}", None),
    (
        "PUT",
        f"/api/attempts/{_DUMMY_ATTEMPT_ID}/answers/{_DUMMY_QUESTION_ID}",
        {"selected_option_id": None},
    ),
    ("POST", f"/api/attempts/{_DUMMY_ATTEMPT_ID}/submit", {"confirm": True}),
    ("GET", f"/api/attempts/{_DUMMY_ATTEMPT_ID}/result", None),
    ("GET", "/api/student/attempts", None),
]

ALL_PROTECTED_ENDPOINTS: list[tuple[str, str, dict[str, object] | None]] = [
    ("GET", "/auth/me", None),
    *ADMIN_ENDPOINTS,
    *STUDENT_ENDPOINTS,
]


@pytest.mark.parametrize(
    "auth_header",
    [
        None,
        "Basic dXNlcjpwYXNz",
        "Token secret-token",
        "Bearer",
        "Bearer   ",
        "Bearer not-even-a-jwt",
        "Bearer aaa.bbb",
    ],
)
def test_sec_auth_01_missing_or_malformed_bearer_rejected_across_all_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    auth_header: str | None,
) -> None:
    headers = {"Authorization": auth_header} if auth_header is not None else {}

    with _build_integrated_env(monkeypatch) as env:
        for method, path, body in ALL_PROTECTED_ENDPOINTS:
            resp = env.client.request(method, path, json=body, headers=headers)
            assert resp.status_code == 401, f"{method} {path} accepted {auth_header!r}"
            assert resp.headers.get("www-authenticate") == "Bearer"

        with env.session_factory() as db:
            users = db.execute(select(ApplicationUser)).scalars().all()
            assert users == []


def test_sec_auth_02_cryptographic_forgery_and_algorithm_confusion_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attacker_ed_key = Ed25519PrivateKey.generate()
    rsa_key = generate_private_key(public_exponent=65537, key_size=2048)

    with _build_integrated_env(monkeypatch) as env:
        wrong_ed_token = _make_eddsa_token(attacker_ed_key, sub="attacker-ed")

        # Classic alg=none unsigned JWT
        alg_none_header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
        now = int(time.time())
        claims_bytes = json.dumps(
            {
                "sub": "attacker-none",
                "iss": "https://auth.example.com",
                "aud": "examination-hub",
                "exp": now + 300,
                "role": "ADMIN",
            }
        ).encode("utf-8")
        alg_none_token = f"{alg_none_header}.{_b64url(claims_bytes)}."

        # Algorithm confusion: HS256 signed with the Ed25519 public key PEM bytes
        pub_pem = env.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        hs_header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
        signing_input = f"{hs_header}.{_b64url(claims_bytes)}".encode("ascii")
        hs_sig = _b64url(hmac.new(pub_pem, signing_input, hashlib.sha256).digest())
        hs_confusion_token = f"{hs_header}.{_b64url(claims_bytes)}.{hs_sig}"

        # RS256 signed token
        rs_token = jwt.encode(
            {
                "sub": "attacker-rsa",
                "iss": "https://auth.example.com",
                "aud": "examination-hub",
                "exp": now + 300,
            },
            rsa_key,
            algorithm="RS256",
        )

        # Tampered payload after valid EdDSA signing
        legit = _make_eddsa_token(env.private_key, sub="student-victim")
        h, _p, s = legit.split(".")
        tampered_payload = _b64url(
            json.dumps(
                {
                    "sub": "admin-target",
                    "iss": "https://auth.example.com",
                    "aud": "examination-hub",
                    "exp": now + 300,
                }
            ).encode("utf-8")
        )
        tampered_token = f"{h}.{tampered_payload}.{s}"

        for bad_token in (
            wrong_ed_token,
            alg_none_token,
            hs_confusion_token,
            rs_token,
            tampered_token,
        ):
            for path in ("/auth/me", "/api/exams", "/api/admin/exams"):
                resp = env.client.get(path, headers={"Authorization": f"Bearer {bad_token}"})
                assert resp.status_code == 401
                assert resp.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize(
    "claim_overrides",
    [
        {"exp_offset": -1},
        {"exp_offset": -300},
        {"exp_offset": None},
        {"nbf_offset": 60},
        {"iss": "https://evil.example.com"},
        {"iss": "https://auth.example.com/"},
        {"aud": "wrong-audience"},
        {"aud": None},
        {"sub": None},
        {"sub": ""},
        {"sub": "   "},
        {"sub": 12345},
    ],
)
def test_sec_auth_03_invalid_claims_rejected(
    monkeypatch: pytest.MonkeyPatch,
    claim_overrides: dict[str, object],
) -> None:
    with _build_integrated_env(monkeypatch) as env:
        bad_token = _make_eddsa_token(env.private_key, **claim_overrides)  # type: ignore[arg-type]
        for path in ("/auth/me", "/api/exams", "/api/admin/exams"):
            resp = env.client.get(path, headers={"Authorization": f"Bearer {bad_token}"})
            assert resp.status_code == 401
            assert resp.headers.get("www-authenticate") == "Bearer"


def test_sec_auth_04_unconfigured_or_jwks_outage_fails_closed_503_and_prod_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unconfigured = Settings(
        _env_file=None,
        APP_ENV="test",
        CORS_ORIGINS=["http://localhost:5173"],
    )
    with _build_integrated_env(monkeypatch, settings=unconfigured) as env:
        for path in ("/auth/me", "/api/exams", "/api/admin/exams"):
            resp = env.client.get(path, headers={"Authorization": "Bearer some.token.val"})
            assert resp.status_code == 503

    with _build_integrated_env(
        monkeypatch,
        jwks_error=jwt.PyJWKClientConnectionError("JWKS unreachable"),
    ) as env:
        for path in ("/auth/me", "/api/exams", "/api/admin/exams"):
            resp = env.client.get(path, headers={"Authorization": "Bearer some.token.val"})
            assert resp.status_code == 503

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="production",
            CORS_ORIGINS=["https://exams.example.com"],
        )


def test_sec_rbac_01_client_role_escalation_attempts_ignored_and_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_integrated_env(monkeypatch) as env:
        escalated_jwt = _make_eddsa_token(
            env.private_key,
            sub="escalate-probe-sub",
            extra_claims={
                "email": "attacker@example.edu",
                "name": "Mallory",
                "role": "ADMIN",
                "roles": ["ADMIN"],
                "app_role": "ADMIN",
                "is_admin": True,
                "permissions": ["admin:*"],
            },
        )
        headers = {
            "Authorization": f"Bearer {escalated_jwt}",
            "X-User-Role": "ADMIN",
            "X-Role": "ADMIN",
        }
        me_resp = env.client.get("/auth/me?role=ADMIN", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["role"] == ROLE_STUDENT

        with env.session_factory() as db:
            user = db.execute(
                select(ApplicationUser).where(
                    ApplicationUser.auth_subject == "escalate-probe-sub"
                )
            ).scalar_one()
            assert user.role == ROLE_STUDENT

        for method, path, body in ADMIN_ENDPOINTS:
            resp = env.client.request(method, path, json=body, headers=headers)
            assert resp.status_code == 403, f"Escalated student bypassed {method} {path}"


def test_sec_rbac_02_exhaustive_student_and_admin_cross_role_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_integrated_env(monkeypatch) as env:
        student_tok = _make_eddsa_token(
            env.private_key,
            sub="strict-student-sub",
            extra_claims={"email": "student@example.edu", "role": "ADMIN"},
        )
        admin_tok = _make_eddsa_token(
            env.private_key,
            sub="strict-admin-sub",
            extra_claims={"email": "admin@example.edu", "role": "STUDENT"},
        )

        # Provision both via /auth/me, then promote admin in DB.
        assert (
            env.client.get(
                "/auth/me", headers={"Authorization": f"Bearer {student_tok}"}
            ).status_code
            == 200
        )
        assert (
            env.client.get("/auth/me", headers={"Authorization": f"Bearer {admin_tok}"}).status_code
            == 200
        )
        with env.session_factory() as db:
            db.execute(
                text("UPDATE application_users SET role = :role WHERE auth_subject = :sub"),
                {"role": ROLE_ADMIN, "sub": "strict-admin-sub"},
            )
            db.commit()

        student_headers = {"Authorization": f"Bearer {student_tok}"}
        admin_headers = {"Authorization": f"Bearer {admin_tok}"}

        for method, path, body in ADMIN_ENDPOINTS:
            resp = env.client.request(method, path, json=body, headers=student_headers)
            assert resp.status_code == 403, f"Student reached admin endpoint {method} {path}"
            assert resp.json()["detail"] == "Admin role required"

        for method, path, body in STUDENT_ENDPOINTS:
            resp = env.client.request(method, path, json=body, headers=admin_headers)
            assert resp.status_code == 403, f"Admin reached student endpoint {method} {path}"
            assert resp.json()["detail"] == "Student role required"


def test_sec_rbac_03_unprovisioned_subject_fails_closed_on_all_admin_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_integrated_env(monkeypatch) as env:
        unprovisioned_tok = _make_eddsa_token(
            env.private_key,
            sub="unprovisioned-admin-probe",
            extra_claims={"role": "ADMIN"},
        )
        headers = {"Authorization": f"Bearer {unprovisioned_tok}"}

        for method, path, body in ADMIN_ENDPOINTS:
            resp = env.client.request(method, path, json=body, headers=headers)
            assert resp.status_code == 401, f"Unprovisioned user not 401 on {method} {path}"
            assert resp.headers.get("www-authenticate") == "Bearer"

        with env.session_factory() as db:
            row = db.execute(
                select(ApplicationUser).where(
                    ApplicationUser.auth_subject == "unprovisioned-admin-probe"
                )
            ).scalar_one_or_none()
            assert row is None


def test_sec_rbac_04_db_role_promotion_and_demotion_take_immediate_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_integrated_env(monkeypatch) as env:
        user_tok = _make_eddsa_token(
            env.private_key,
            sub="role-switch-sub",
            extra_claims={"email": "switch@example.edu", "role": "ADMIN"},
        )
        headers = {"Authorization": f"Bearer {user_tok}"}

        # Initial /auth/me -> STUDENT -> admin endpoint 403
        assert env.client.get("/auth/me", headers=headers).json()["role"] == ROLE_STUDENT
        assert env.client.get("/api/admin/exams", headers=headers).status_code == 403

        # Promote in DB -> /auth/me preserves ADMIN even with conflicting token claim
        with env.session_factory() as db:
            db.execute(
                text("UPDATE application_users SET role = :role WHERE auth_subject = :sub"),
                {"role": ROLE_ADMIN, "sub": "role-switch-sub"},
            )
            db.commit()

        student_claim_tok = _make_eddsa_token(
            env.private_key,
            sub="role-switch-sub",
            extra_claims={"role": "STUDENT"},
        )
        admin_headers = {"Authorization": f"Bearer {student_claim_tok}"}
        assert env.client.get("/auth/me", headers=admin_headers).json()["role"] == ROLE_ADMIN
        assert env.client.get("/api/admin/exams", headers=admin_headers).status_code == 200

        # Demote back to STUDENT -> previously working token is immediately blocked
        with env.session_factory() as db:
            db.execute(
                text("UPDATE application_users SET role = :role WHERE auth_subject = :sub"),
                {"role": ROLE_STUDENT, "sub": "role-switch-sub"},
            )
            db.commit()

        assert env.client.get("/api/admin/exams", headers=headers).status_code == 403
        assert env.client.get("/api/exams", headers=headers).status_code == 200
