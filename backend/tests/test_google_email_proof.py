"""Independent proof gate and remote OTP rejection tests; no Neon calls."""

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest
from fastapi import HTTPException

from app.auth import google_email_proof as proof
from app.auth.dependencies import AuthIdentity
from app.config import Settings


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class Database:
    def __init__(self, results):
        self.results = iter(results)
        self.statements = []
        self.committed = False

    def get_bind(self):
        return type("Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        return Result(next(self.results, None))

    def commit(self):
        self.committed = True


IDENTITY = AuthIdentity(subject="google-user", email="student@example.test", name="Student")
ORIGIN = "https://exam.example.test"


def test_google_session_is_denied_until_matching_email_proof():
    with pytest.raises(HTTPException, match="GOOGLE_EMAIL_PROOF_REQUIRED"):
        proof.require_google_email_proof(Database([1, None]), IDENTITY)
    with pytest.raises(HTTPException, match="GOOGLE_EMAIL_PROOF_REQUIRED"):
        proof.require_google_email_proof(Database([1, "old@example.test"]), IDENTITY)
    proof.require_google_email_proof(Database([1, "STUDENT@example.test"]), IDENTITY)
    proof.require_google_email_proof(Database([None]), IDENTITY)


def test_wrong_code_never_records_proof(monkeypatch):
    db = Database([])
    monkeypatch.setattr(proof, "google_email_needs_proof", lambda *_: True)

    def reject(*_args, **_kwargs):
        raise HTTPError("https://auth.example.test", 400, "invalid", None, None)

    monkeypatch.setattr(proof, "urlopen", reject)
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        NEON_AUTH_BASE_URL="https://auth.example.test",
        CORS_ORIGINS=[ORIGIN],
    )
    with pytest.raises(HTTPException) as error:
        proof.confirm_google_email_and_password(
            db,
            IDENTITY,
            settings,
            "000000",
            "fake-test-password",
            origin=ORIGIN,
        )
    assert error.value.status_code == 400
    assert not db.committed and not db.statements


@pytest.mark.parametrize("body", [b'{"success":false}', b"{}", b"not-json"])
def test_provider_must_confirm_success_before_recording_proof(monkeypatch, body):
    monkeypatch.setattr(proof, "google_email_needs_proof", lambda *_: True)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return body

    monkeypatch.setattr(proof, "urlopen", lambda *_args, **_kwargs: Response())
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        NEON_AUTH_BASE_URL="https://auth.example.test",
        CORS_ORIGINS=[ORIGIN],
    )
    db = Database([])
    with pytest.raises(HTTPException) as error:
        proof.confirm_google_email_and_password(
            db,
            IDENTITY,
            settings,
            "123456",
            "fake-test-password",
            origin=ORIGIN,
        )
    assert error.value.status_code == 502
    assert not db.committed and not db.statements


def test_proof_endpoint_forwards_browser_origin(monkeypatch):
    from fastapi.testclient import TestClient

    from app.auth.dependencies import require_identity
    from app.database.session import get_db
    from app.main import create_app

    app = create_app(Settings(_env_file=None, APP_ENV="test", CORS_ORIGINS=[ORIGIN]))
    app.dependency_overrides[require_identity] = lambda: IDENTITY
    app.dependency_overrides[get_db] = lambda: Database([])
    seen = []
    monkeypatch.setattr(
        proof,
        "confirm_google_email_and_password",
        lambda *_args, **kwargs: seen.append(kwargs["origin"]),
    )
    response = TestClient(app).post(
        "/auth/google-email-proof",
        headers={"Origin": ORIGIN},
        json={"otp": "123456", "password": "fake-test-password"},
    )
    assert response.status_code == 204
    assert seen == [ORIGIN]


def test_valid_code_records_subject_and_verified_email(monkeypatch):
    db = Database([None])
    monkeypatch.setattr(proof, "google_email_needs_proof", lambda *_: True)
    seen = {}

    class Response:
        status = 200

        def read(self, _limit):
            return b'{"success":true}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def accept(request, timeout):
        seen.update(json.loads(request.data))
        assert timeout == 8
        assert request.get_header("Origin") == ORIGIN
        return Response()

    monkeypatch.setattr(proof, "urlopen", accept)
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        NEON_AUTH_BASE_URL="https://auth.example.test",
        CORS_ORIGINS=[ORIGIN],
    )
    proof.confirm_google_email_and_password(
        db,
        IDENTITY,
        settings,
        "123456",
        "fake-test-password",
        origin=ORIGIN,
    )
    assert seen == {"email": IDENTITY.email, "otp": "123456", "password": "fake-test-password"}
    assert db.committed
    assert len(db.statements) == 2


@pytest.mark.parametrize(
    "origin", [None, "https://attacker.example.test", ORIGIN + ".attacker.test"]
)
def test_untrusted_origin_never_reaches_password_provider(monkeypatch, origin):
    monkeypatch.setattr(proof, "google_email_needs_proof", lambda *_: True)

    def unexpected(*_args, **_kwargs):
        pytest.fail("Untrusted request reached provider")

    monkeypatch.setattr(proof, "urlopen", unexpected)
    settings = Settings(_env_file=None, APP_ENV="test", CORS_ORIGINS=[ORIGIN])
    db = Database([])
    with pytest.raises(HTTPException) as error:
        proof.confirm_google_email_and_password(
            db,
            IDENTITY,
            settings,
            "123456",
            "fake-test-password",
            origin=origin,
        )
    assert error.value.status_code == 403
    assert not db.committed


@pytest.mark.parametrize(
    ("status", "code", "expected", "message"),
    [
        (400, "OTP_EXPIRED", 400, "expired"),
        (400, "INVALID_OTP", 400, "incorrect"),
        (400, "PASSWORD_TOO_SHORT", 400, "8 characters"),
        (429, "TOO_MANY_REQUESTS", 429, "Too many"),
        (400, "MISSING_ORIGIN", 502, "configuration"),
        (503, "UNKNOWN", 503, "temporarily unavailable"),
    ],
)
def test_provider_errors_are_safe_and_do_not_record_proof(
    monkeypatch, status, code, expected, message
):
    monkeypatch.setattr(proof, "google_email_needs_proof", lambda *_: True)

    def reject(*_args, **_kwargs):
        body = BytesIO(json.dumps({"code": code, "message": "private provider detail"}).encode())
        raise HTTPError("https://auth.example.test", status, "rejected", None, body)

    monkeypatch.setattr(proof, "urlopen", reject)
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        NEON_AUTH_BASE_URL="https://auth.example.test",
        CORS_ORIGINS=[ORIGIN],
    )
    db = Database([])
    with pytest.raises(HTTPException) as error:
        proof.confirm_google_email_and_password(
            db, IDENTITY, settings, "123456", "fake-test-password", origin=ORIGIN
        )
    assert error.value.status_code == expected
    assert message in error.value.detail
    assert "private provider detail" not in error.value.detail
    assert not db.committed and not db.statements
