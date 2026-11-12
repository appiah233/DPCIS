"""Comprehensive integration, security, timer, and concurrency tests for attempts."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.database  # noqa: F401
from app.attempts import router as attempts_router
from app.attempts import service as attempt_service
from app.attempts.models import AttemptQuestion, ExamAttempt, StudentAnswer
from app.auth import ROLE_ADMIN, ROLE_STUDENT, AuthIdentity
from app.auth import dependencies as auth_dependencies
from app.config import Settings
from app.database import Base
from app.database.session import get_db
from app.exams import router as exams_router
from app.exams.models import Exam, QuestionOption
from app.main import create_app
from app.users.models import ApplicationUser

ACTIVE_FORBIDDEN_KEYS = {
    "is_correct",
    "correct_option_id",
    "pass_mark",
    "answer_label",
}

HIDDEN_SCORE_KEYS = {
    "correct_answers",
    "incorrect_answers",
    "unanswered_questions",
    "points_earned",
    "points_available",
    "percentage",
    "pass_mark",
    "passed",
    "question_review",
    "is_correct",
    "correct_option_id",
}


def _assert_no_keys(payload: object, forbidden: set[str]) -> None:
    if isinstance(payload, dict):
        for key, val in payload.items():
            assert key not in forbidden, f"Forbidden key leaked: {key}"
            _assert_no_keys(val, forbidden)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_keys(item, forbidden)


def _auth_settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        CORS_ORIGINS=["http://localhost:5173"],
        NEON_AUTH_BASE_URL="https://auth.example.com",
        NEON_AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
        NEON_AUTH_AUDIENCE="examination-hub",
    )


def _make_token(
    private_key: Ed25519PrivateKey,
    *,
    sub: str,
    email: str | None = None,
    name: str | None = None,
    extra_claims: dict[str, object] | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": sub,
        "iss": "https://auth.example.com",
        "aud": "examination-hub",
        "exp": now + 300,
    }
    if email is not None:
        payload["email"] = email
    if name is not None:
        payload["name"] = name
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, private_key, algorithm="EdDSA")


def _sample_question(
    text: str,
    *,
    position: int,
    points: str = "1.00",
    correct_label: str = "B",
) -> dict[str, object]:
    return {
        "question_text": text,
        "position": position,
        "points": points,
        "options": [
            {"label": "A", "option_text": f"{text} opt A", "is_correct": correct_label == "A"},
            {"label": "B", "option_text": f"{text} opt B", "is_correct": correct_label == "B"},
            {"label": "C", "option_text": f"{text} opt C", "is_correct": correct_label == "C"},
            {"label": "D", "option_text": f"{text} opt D", "is_correct": correct_label == "D"},
        ],
    }


@pytest.fixture
def attempt_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    monkeypatch.setattr(
        auth_dependencies,
        "_jwks_client",
        lambda _url: SimpleNamespace(
            get_signing_key_from_jwt=lambda _tok: SimpleNamespace(key=public_key)
        ),
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_connection, _record) -> None:
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

    admin_id = uuid4()
    student_a_id = uuid4()
    student_b_id = uuid4()
    with session_factory() as db:
        db.add_all(
            [
                ApplicationUser(
                    id=admin_id,
                    auth_subject="neon_admin_sub",
                    email="admin@example.edu",
                    display_name="Exam Admin",
                    role=ROLE_ADMIN,
                ),
                ApplicationUser(
                    id=student_a_id,
                    auth_subject="neon_student_a",
                    email="alice@example.edu",
                    display_name="Alice Student",
                    role=ROLE_STUDENT,
                ),
                ApplicationUser(
                    id=student_b_id,
                    auth_subject="neon_student_b",
                    email="bob@example.edu",
                    display_name="Bob Student",
                    role=ROLE_STUDENT,
                ),
            ]
        )
        db.commit()

    def _override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app(settings=_auth_settings())
    app.include_router(exams_router.router)
    app.include_router(attempts_router.router)
    app.dependency_overrides[get_db] = _override_get_db

    admin_token = _make_token(private_key, sub="neon_admin_sub", email="admin@example.edu")
    student_a_token = _make_token(
        private_key,
        sub="neon_student_a",
        email="alice@example.edu",
        extra_claims={"role": "ADMIN"},  # Must be ignored in favor of DB role
    )
    student_b_token = _make_token(private_key, sub="neon_student_b", email="bob@example.edu")
    new_student_token = _make_token(
        private_key,
        sub="neon_student_new_sub",
        email="charlie@example.edu",
        name="Charlie New",
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(
            client=client,
            session_factory=session_factory,
            admin_id=admin_id,
            student_a_id=student_a_id,
            student_b_id=student_b_id,
            admin_headers={"Authorization": f"Bearer {admin_token}"},
            student_a_headers={"Authorization": f"Bearer {student_a_token}"},
            student_b_headers={"Authorization": f"Bearer {student_b_token}"},
            new_student_headers={"Authorization": f"Bearer {new_student_token}"},
        )

    engine.dispose()


def _create_and_publish_exam(
    env: SimpleNamespace,
    *,
    title: str = "Algorithms Midterm",
    duration_minutes: int = 30,
    pass_mark: str | Decimal = Decimal("50.00"),
    question_limit: int | None = None,
    randomize_questions: bool = False,
    randomize_options: bool = False,
    max_attempts: int = 2,
    show_result: bool = True,
    show_correct_answers: bool = False,
    questions: list[dict[str, object]] | None = None,
    publish: bool = True,
) -> dict[str, object]:
    create_resp = env.client.post(
        "/api/admin/exams",
        headers=env.admin_headers,
        json={
            "title": title,
            "duration_minutes": duration_minutes,
            "pass_mark": str(pass_mark),
            "question_limit": question_limit,
            "randomize_questions": randomize_questions,
            "randomize_options": randomize_options,
            "max_attempts": max_attempts,
            "show_result": show_result,
            "show_correct_answers": show_correct_answers,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    exam_id = create_resp.json()["id"]

    payload_questions = questions or [
        _sample_question("Q1", position=1, points="2.00", correct_label="A"),
        _sample_question("Q2", position=2, points="2.00", correct_label="B"),
        _sample_question("Q3", position=3, points="1.00", correct_label="C"),
    ]
    put_resp = env.client.put(
        f"/api/admin/exams/{exam_id}/questions",
        headers=env.admin_headers,
        json={"questions": payload_questions},
    )
    assert put_resp.status_code == 200, put_resp.text

    if publish:
        pub_resp = env.client.post(
            f"/api/admin/exams/{exam_id}/publish",
            headers=env.admin_headers,
        )
        assert pub_resp.status_code == 200, pub_resp.text

    detail_resp = env.client.get(
        f"/api/admin/exams/{exam_id}",
        headers=env.admin_headers,
    )
    assert detail_resp.status_code == 200
    return detail_resp.json()


# ---------------------------------------------------------------------------
# Auth, Role & Identity Resolution Guards
# ---------------------------------------------------------------------------


def test_attempts_auth_and_role_isolation(attempt_env: SimpleNamespace) -> None:
    exam = _create_and_publish_exam(attempt_env)
    exam_id = exam["id"]
    fake_attempt_id = str(uuid4())
    fake_question_id = str(uuid4())

    # Unauthenticated -> 401
    assert attempt_env.client.post(f"/api/exams/{exam_id}/attempts").status_code == 401
    assert attempt_env.client.get(f"/api/attempts/{fake_attempt_id}").status_code == 401
    assert (
        attempt_env.client.put(
            f"/api/attempts/{fake_attempt_id}/answers/{fake_question_id}",
            json={"selected_option_id": None},
        ).status_code
        == 401
    )
    assert attempt_env.client.post(f"/api/attempts/{fake_attempt_id}/submit").status_code == 401
    assert attempt_env.client.get(f"/api/attempts/{fake_attempt_id}/result").status_code == 401
    assert attempt_env.client.get("/api/student/attempts").status_code == 401
    assert attempt_env.client.get(f"/api/admin/exams/{exam_id}/results").status_code == 401
    assert attempt_env.client.get(f"/api/admin/attempts/{fake_attempt_id}").status_code == 401

    # Admin calling student attempt routes -> 403
    assert (
        attempt_env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=attempt_env.admin_headers,
        ).status_code
        == 403
    )
    assert (
        attempt_env.client.get(
            "/api/student/attempts",
            headers=attempt_env.admin_headers,
        ).status_code
        == 403
    )

    # Student calling admin results routes -> 403
    assert (
        attempt_env.client.get(
            f"/api/admin/exams/{exam_id}/results",
            headers=attempt_env.student_a_headers,
        ).status_code
        == 403
    )
    assert (
        attempt_env.client.get(
            f"/api/admin/attempts/{fake_attempt_id}",
            headers=attempt_env.student_a_headers,
        ).status_code
        == 403
    )

    # Service-level identity helper fails closed without application_users.id UUID
    with pytest.raises(HTTPException) as missing_exc:
        attempt_service.require_student_user_id(
            AuthIdentity(subject="sub", email=None, name=None, role=ROLE_STUDENT, user_id=None)
        )
    assert missing_exc.value.status_code == 401

    with pytest.raises(HTTPException) as wrong_role_exc:
        attempt_service.require_admin_user_id(
            AuthIdentity(
                subject="sub",
                email=None,
                name=None,
                role=ROLE_STUDENT,
                user_id=attempt_env.student_a_id,
            )
        )
    assert wrong_role_exc.value.status_code == 403

    # Unprovisioned student auto-provisions and stores application_users.id UUID (not subject)
    start_resp = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.new_student_headers,
    )
    assert start_resp.status_code == 201
    attempt_uuid = UUID(start_resp.json()["attempt_id"])
    with attempt_env.session_factory() as db:
        attempt_row = db.get(ExamAttempt, attempt_uuid)
        user_row = db.execute(
            select(ApplicationUser).where(
                ApplicationUser.auth_subject == "neon_student_new_sub"
            )
        ).scalar_one()
        assert attempt_row is not None
        assert attempt_row.user_id == user_row.id


# ---------------------------------------------------------------------------
# Eligibility, Resume Invariant & Lazy Expiry Max-Attempt Enforcement
# ---------------------------------------------------------------------------


def test_start_attempt_eligibility_resume_and_lazy_expiry_max_attempts(
    attempt_env: SimpleNamespace,
) -> None:
    draft_exam = _create_and_publish_exam(attempt_env, title="Draft Exam", publish=False)
    closed_exam = _create_and_publish_exam(attempt_env, title="Closed Exam", publish=True)
    assert (
        attempt_env.client.post(
            f"/api/admin/exams/{closed_exam['id']}/close",
            headers=attempt_env.admin_headers,
        ).status_code
        == 200
    )

    # Draft/unknown -> 404; closed -> 400
    assert (
        attempt_env.client.post(
            f"/api/exams/{draft_exam['id']}/attempts",
            headers=attempt_env.student_a_headers,
        ).status_code
        == 404
    )
    assert (
        attempt_env.client.post(
            f"/api/exams/{uuid4()}/attempts",
            headers=attempt_env.student_a_headers,
        ).status_code
        == 404
    )
    assert (
        attempt_env.client.post(
            f"/api/exams/{closed_exam['id']}/attempts",
            headers=attempt_env.student_a_headers,
        ).status_code
        == 400
    )

    published = _create_and_publish_exam(
        attempt_env,
        title="Max Two Attempts",
        duration_minutes=25,
        max_attempts=2,
    )
    exam_id = published["id"]

    # Tampered start body (client clock / user override) rejected with 422
    assert (
        attempt_env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=attempt_env.student_a_headers,
            json={"started_at": "2099-01-01T00:00:00Z"},
        ).status_code
        == 422
    )

    # Start #1 -> 201
    start1 = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_a_headers,
    )
    assert start1.status_code == 201
    s1 = start1.json()
    assert s1["resumed"] is False
    assert s1["status"] == "IN_PROGRESS"
    assert s1["total_questions"] == 3
    started_at_1 = datetime.fromisoformat(s1["started_at"])
    expires_at_1 = datetime.fromisoformat(s1["expires_at"])
    assert expires_at_1 - started_at_1 == timedelta(minutes=25)

    # Double-start / second tab while active -> 200 resumed=True, identical attempt & deadline
    resume1 = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_a_headers,
    )
    assert resume1.status_code == 200
    r1 = resume1.json()
    assert r1["resumed"] is True
    assert r1["attempt_id"] == s1["attempt_id"]
    assert r1["started_at"] == s1["started_at"]
    assert r1["expires_at"] == s1["expires_at"]

    # Force expiry on Attempt #1 -> next start lazily finalizes #1 as TIMER_EXPIRED and creates #2
    with attempt_env.session_factory() as db:
        att1 = db.get(ExamAttempt, UUID(s1["attempt_id"]))
        assert att1 is not None
        att1.expires_at = datetime.now(UTC) - timedelta(seconds=5)
        db.commit()

    start2 = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_a_headers,
    )
    assert start2.status_code == 201
    s2 = start2.json()
    assert s2["resumed"] is False
    assert s2["attempt_id"] != s1["attempt_id"]

    with attempt_env.session_factory() as db:
        att1_after = db.get(ExamAttempt, UUID(s1["attempt_id"]))
        assert att1_after is not None
        assert att1_after.status == "GRADED"
        assert att1_after.submission_reason == "TIMER_EXPIRED"

    # Force expiry on Attempt #2 -> next start lazily finalizes #2 AND enforces max_attempts=2 (409)
    with attempt_env.session_factory() as db:
        att2 = db.get(ExamAttempt, UUID(s2["attempt_id"]))
        assert att2 is not None
        att2.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    start3 = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_a_headers,
    )
    assert start3.status_code == 409
    assert "Maximum number of attempts" in start3.json()["detail"]

    with attempt_env.session_factory() as db:
        att2_after = db.get(ExamAttempt, UUID(s2["attempt_id"]))
        assert att2_after is not None
        assert att2_after.status == "GRADED"
        assert att2_after.submission_reason == "TIMER_EXPIRED"


# ---------------------------------------------------------------------------
# Frozen Snapshot, Option Normalization & Saved Answers on Refresh
# ---------------------------------------------------------------------------


def test_delivery_frozen_snapshot_normalized_labels_and_saved_answers(
    attempt_env: SimpleNamespace,
) -> None:
    questions = [
        _sample_question(f"Question {i}", position=i, points="2.00", correct_label="C")
        for i in range(1, 6)
    ]
    exam = _create_and_publish_exam(
        attempt_env,
        title="Randomized Snapshot Exam",
        duration_minutes=45,
        question_limit=3,
        randomize_questions=True,
        randomize_options=True,
        max_attempts=1,
        questions=questions,
    )
    exam_id = exam["id"]

    start_resp = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_a_headers,
    )
    assert start_resp.status_code == 201
    attempt_id = start_resp.json()["attempt_id"]

    # option_order must be populated as JSON UUID list in attempt_questions
    with attempt_env.session_factory() as db:
        aqs = list(
            db.execute(
                select(AttemptQuestion)
                .where(AttemptQuestion.attempt_id == UUID(attempt_id))
                .order_by(AttemptQuestion.display_order)
            ).scalars().all()
        )
        assert len(aqs) == 3
        for idx, aq in enumerate(aqs):
            assert aq.display_order == idx
            assert aq.option_order is not None
            parsed = json.loads(aq.option_order)
            assert len(parsed) == 4

    deliv1_resp = attempt_env.client.get(
        f"/api/attempts/{attempt_id}",
        headers=attempt_env.student_a_headers,
    )
    assert deliv1_resp.status_code == 200
    deliv1 = deliv1_resp.json()
    _assert_no_keys(deliv1, ACTIVE_FORBIDDEN_KEYS)

    assert deliv1["attempt_id"] == attempt_id
    assert deliv1["exam_id"] == exam_id
    assert deliv1["exam_title"] == "Randomized Snapshot Exam"
    assert deliv1["duration_minutes"] == 45
    assert deliv1["status"] == "IN_PROGRESS"
    assert deliv1["total_questions"] == 3
    assert deliv1["saved_answers"] == {}
    assert len(deliv1["questions"]) == 3

    for idx, q in enumerate(deliv1["questions"]):
        assert q["display_order"] == idx
        assert [opt["label"] for opt in q["options"]] == ["A", "B", "C", "D"]

    # Save selections for Q0 and Q1
    q0_id = deliv1["questions"][0]["id"]
    q0_opt_id = deliv1["questions"][0]["options"][2]["id"]
    q1_id = deliv1["questions"][1]["id"]
    q1_opt_id = deliv1["questions"][1]["options"][0]["id"]

    assert (
        attempt_env.client.put(
            f"/api/attempts/{attempt_id}/answers/{q0_id}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": q0_opt_id},
        ).status_code
        == 200
    )
    assert (
        attempt_env.client.put(
            f"/api/attempts/{attempt_id}/answers/{q1_id}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": q1_opt_id},
        ).status_code
        == 200
    )

    # Refresh/reopen delivery & resume start -> identical snapshot, order, deadline & answers
    resume_resp = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_a_headers,
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["attempt_id"] == attempt_id

    deliv2_resp = attempt_env.client.get(
        f"/api/attempts/{attempt_id}",
        headers=attempt_env.student_a_headers,
    )
    assert deliv2_resp.status_code == 200
    deliv2 = deliv2_resp.json()
    _assert_no_keys(deliv2, ACTIVE_FORBIDDEN_KEYS)

    assert deliv2["started_at"] == deliv1["started_at"]
    assert deliv2["expires_at"] == deliv1["expires_at"]
    assert [q["id"] for q in deliv2["questions"]] == [q["id"] for q in deliv1["questions"]]
    for q1, q2 in zip(deliv1["questions"], deliv2["questions"], strict=True):
        assert [o["id"] for o in q2["options"]] == [o["id"] for o in q1["options"]]
        assert [o["label"] for o in q2["options"]] == ["A", "B", "C", "D"]
    assert deliv2["saved_answers"] == {q0_id: q0_opt_id, q1_id: q1_opt_id}


def test_non_randomized_snapshot_freezes_positional_option_order(
    attempt_env: SimpleNamespace,
) -> None:
    exam = _create_and_publish_exam(
        attempt_env,
        randomize_questions=False,
        randomize_options=False,
    )
    start_resp = attempt_env.client.post(
        f"/api/exams/{exam['id']}/attempts",
        headers=attempt_env.student_a_headers,
    )
    assert start_resp.status_code == 201
    attempt_id = start_resp.json()["attempt_id"]

    with attempt_env.session_factory() as db:
        aqs = list(
            db.execute(
                select(AttemptQuestion)
                .where(AttemptQuestion.attempt_id == UUID(attempt_id))
                .order_by(AttemptQuestion.display_order)
            ).scalars().all()
        )
        for aq, exam_q in zip(aqs, exam["questions"], strict=True):
            assert str(aq.question_id) == exam_q["id"]
            assert aq.option_order == json.dumps([o["id"] for o in exam_q["options"]])

    deliv = attempt_env.client.get(
        f"/api/attempts/{attempt_id}",
        headers=attempt_env.student_a_headers,
    ).json()
    for delivered_q, exam_q in zip(deliv["questions"], exam["questions"], strict=True):
        assert delivered_q["id"] == exam_q["id"]
        assert [o["id"] for o in delivered_q["options"]] == [o["id"] for o in exam_q["options"]]


# ---------------------------------------------------------------------------
# Autosave Idempotency, Validation & Timer Enforcement
# ---------------------------------------------------------------------------


def test_autosave_idempotency_validation_and_timer_expiry_lock(
    attempt_env: SimpleNamespace,
) -> None:
    other_exam = _create_and_publish_exam(attempt_env, title="Other Exam")
    exam = _create_and_publish_exam(
        attempt_env,
        title="Main Exam",
        question_limit=2,
        randomize_questions=False,
    )
    attempt_id = attempt_env.client.post(
        f"/api/exams/{exam['id']}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]

    deliv = attempt_env.client.get(
        f"/api/attempts/{attempt_id}",
        headers=attempt_env.student_a_headers,
    ).json()
    q0 = deliv["questions"][0]
    q1 = deliv["questions"][1]
    opt_a = q0["options"][0]["id"]
    opt_b = q0["options"][1]["id"]
    q1_opt = q1["options"][0]["id"]
    excluded_q_id = exam["questions"][2]["id"]
    other_exam_q_id = other_exam["questions"][0]["id"]

    # Insert A
    save1 = attempt_env.client.put(
        f"/api/attempts/{attempt_id}/answers/{q0['id']}",
        headers=attempt_env.student_a_headers,
        json={"selected_option_id": opt_a},
    )
    assert save1.status_code == 200
    s1_json = save1.json()
    _assert_no_keys(s1_json, ACTIVE_FORBIDDEN_KEYS)
    assert s1_json["selected_option_id"] == opt_a

    # Update A -> B preserves answered_at and advances updated_at
    time.sleep(0.01)
    save2 = attempt_env.client.put(
        f"/api/attempts/{attempt_id}/answers/{q0['id']}",
        headers=attempt_env.student_a_headers,
        json={"selected_option_id": opt_b},
    )
    assert save2.status_code == 200
    s2_json = save2.json()
    assert s2_json["selected_option_id"] == opt_b
    assert s2_json["answered_at"] == s1_json["answered_at"]
    assert s2_json["updated_at"] >= s1_json["updated_at"]

    # Clear B -> None
    save3 = attempt_env.client.put(
        f"/api/attempts/{attempt_id}/answers/{q0['id']}",
        headers=attempt_env.student_a_headers,
        json={"selected_option_id": None},
    )
    assert save3.status_code == 200
    assert save3.json()["selected_option_id"] is None

    # Save valid opt_a again before testing expiry
    assert (
        attempt_env.client.put(
            f"/api/attempts/{attempt_id}/answers/{q0['id']}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": opt_a},
        ).status_code
        == 200
    )

    # Extra tampered payload keys rejected with 422
    for bad_payload in (
        {"selected_option_id": opt_a, "score": 100},
        {"selected_option_id": opt_a, "is_correct": True},
        {"selected_option_id": opt_a, "percentage": "100.00"},
    ):
        assert (
            attempt_env.client.put(
                f"/api/attempts/{attempt_id}/answers/{q0['id']}",
                headers=attempt_env.student_a_headers,
                json=bad_payload,
            ).status_code
            == 422
        )

    # Question outside frozen snapshot or from other exam -> 400
    assert (
        attempt_env.client.put(
            f"/api/attempts/{attempt_id}/answers/{excluded_q_id}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": None},
        ).status_code
        == 400
    )
    assert (
        attempt_env.client.put(
            f"/api/attempts/{attempt_id}/answers/{other_exam_q_id}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": None},
        ).status_code
        == 400
    )

    # Cross-question option injection -> 400
    assert (
        attempt_env.client.put(
            f"/api/attempts/{attempt_id}/answers/{q0['id']}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": q1_opt},
        ).status_code
        == 400
    )

    # Server clock at/past expires_at -> rejects save with 409 AND durably finalizes TIMER_EXPIRED
    with attempt_env.session_factory() as db:
        att = db.get(ExamAttempt, UUID(attempt_id))
        assert att is not None
        att.expires_at = datetime.now(UTC) - timedelta(microseconds=1)
        db.commit()

    expired_save = attempt_env.client.put(
        f"/api/attempts/{attempt_id}/answers/{q0['id']}",
        headers=attempt_env.student_a_headers,
        json={"selected_option_id": opt_b},
    )
    assert expired_save.status_code == 409
    assert expired_save.json()["code"] == "ATTEMPT_EXPIRED"
    assert expired_save.json()["status"] == "GRADED"

    # Saved answer must still be opt_a, NOT opt_b, and attempt must be GRADED
    with attempt_env.session_factory() as db:
        att = db.get(ExamAttempt, UUID(attempt_id))
        ans = db.execute(
            select(StudentAnswer).where(
                StudentAnswer.attempt_id == UUID(attempt_id),
                StudentAnswer.question_id == UUID(q0["id"]),
            )
        ).scalar_one()
        assert att is not None
        assert att.status == "GRADED"
        assert att.submission_reason == "TIMER_EXPIRED"
        assert ans.selected_option_id == UUID(opt_a)

    # Delivery & further save on GRADED attempt return 409 ATTEMPT_ALREADY_GRADED
    deliv_after = attempt_env.client.get(
        f"/api/attempts/{attempt_id}",
        headers=attempt_env.student_a_headers,
    )
    assert deliv_after.status_code == 409
    assert deliv_after.json()["code"] == "ATTEMPT_ALREADY_GRADED"
    assert deliv_after.json()["status"] == "GRADED"

    save_after = attempt_env.client.put(
        f"/api/attempts/{attempt_id}/answers/{q0['id']}",
        headers=attempt_env.student_a_headers,
        json={"selected_option_id": opt_b},
    )
    assert save_after.status_code == 409
    assert save_after.json()["code"] == "ATTEMPT_ALREADY_GRADED"


# ---------------------------------------------------------------------------
# Cross-Student IDOR Isolation
# ---------------------------------------------------------------------------


def test_cross_student_idor_blocked_everywhere(attempt_env: SimpleNamespace) -> None:
    exam = _create_and_publish_exam(attempt_env)
    attempt_id = attempt_env.client.post(
        f"/api/exams/{exam['id']}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]
    q0_id = exam["questions"][0]["id"]
    q0_opt_id = exam["questions"][0]["options"][0]["id"]

    # Student B cannot read, save, submit, or view result for Student A's attempt
    assert (
        attempt_env.client.get(
            f"/api/attempts/{attempt_id}",
            headers=attempt_env.student_b_headers,
        ).status_code
        == 404
    )
    assert (
        attempt_env.client.put(
            f"/api/attempts/{attempt_id}/answers/{q0_id}",
            headers=attempt_env.student_b_headers,
            json={"selected_option_id": q0_opt_id},
        ).status_code
        == 404
    )
    assert (
        attempt_env.client.post(
            f"/api/attempts/{attempt_id}/submit",
            headers=attempt_env.student_b_headers,
        ).status_code
        == 404
    )
    assert (
        attempt_env.client.get(
            f"/api/attempts/{attempt_id}/result",
            headers=attempt_env.student_b_headers,
        ).status_code
        == 404
    )

    # Student B history is empty
    hist_b = attempt_env.client.get(
        "/api/student/attempts",
        headers=attempt_env.student_b_headers,
    )
    assert hist_b.status_code == 200
    assert hist_b.json() == []


# ---------------------------------------------------------------------------
# Submit Idempotency, Immutability, Timer Delivery & Result Gating
# ---------------------------------------------------------------------------


def test_submit_idempotency_immutability_and_result_disclosure(
    attempt_env: SimpleNamespace,
) -> None:
    # 1) show_result=True, show_correct_answers=False
    exam1 = _create_and_publish_exam(
        attempt_env,
        title="Scores Visible Key Hidden",
        pass_mark="60.00",
        show_result=True,
        show_correct_answers=False,
    )
    a1_id = attempt_env.client.post(
        f"/api/exams/{exam1['id']}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]

    # Cannot view result while IN_PROGRESS & unexpired
    assert (
        attempt_env.client.get(
            f"/api/attempts/{a1_id}/result",
            headers=attempt_env.student_a_headers,
        ).status_code
        == 409
    )

    # Answer Q1 (2 pts, correct='A') and Q2 (2 pts, wrong='A') -> 2.00/5.00 = 40.00%, failed
    q1, q2, _q3 = exam1["questions"]
    assert (
        attempt_env.client.put(
            f"/api/attempts/{a1_id}/answers/{q1['id']}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": q1["options"][0]["id"]},
        ).status_code
        == 200
    )
    assert (
        attempt_env.client.put(
            f"/api/attempts/{a1_id}/answers/{q2['id']}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": q2["options"][0]["id"]},
        ).status_code
        == 200
    )

    # Tampered submit rejected (422); unconfirmed submit rejected (400)
    assert (
        attempt_env.client.post(
            f"/api/attempts/{a1_id}/submit",
            headers=attempt_env.student_a_headers,
            json={"score": 100},
        ).status_code
        == 422
    )
    assert (
        attempt_env.client.post(
            f"/api/attempts/{a1_id}/submit",
            headers=attempt_env.student_a_headers,
            json={"confirm": False},
        ).status_code
        == 400
    )

    # Empty body submit succeeds cleanly
    sub1 = attempt_env.client.post(
        f"/api/attempts/{a1_id}/submit",
        headers=attempt_env.student_a_headers,
    )
    assert sub1.status_code == 200
    sub1_json = sub1.json()
    assert sub1_json["status"] == "GRADED"
    assert sub1_json["submission_reason"] == "STUDENT_SUBMITTED"
    assert sub1_json["result_visible"] is True
    assert sub1_json["show_correct_answers"] is False
    assert sub1_json["question_review"] is None
    assert sub1_json["points_earned"] == "2.00"
    assert sub1_json["points_available"] == "5.00"
    assert sub1_json["percentage"] == "40.00"
    assert sub1_json["passed"] is False
    assert sub1_json["correct_answers"] == 1
    assert sub1_json["incorrect_answers"] == 1
    assert sub1_json["unanswered_questions"] == 1
    _assert_no_keys(sub1_json, {"is_correct", "correct_option_id"})

    # Mutate underlying option correctness in DB -> duplicate submit & result MUST stay immutable
    with attempt_env.session_factory() as db:
        prev_correct = db.get(QuestionOption, UUID(q2["options"][1]["id"]))
        wrong_opt = db.get(QuestionOption, UUID(q2["options"][0]["id"]))
        assert prev_correct is not None
        assert wrong_opt is not None
        prev_correct.is_correct = False
        db.flush()
        wrong_opt.is_correct = True
        db.commit()

    sub1_dup = attempt_env.client.post(
        f"/api/attempts/{a1_id}/submit",
        headers=attempt_env.student_a_headers,
        json={"confirm": True},
    )
    assert sub1_dup.status_code == 200
    assert sub1_dup.json() == sub1_json

    res1 = attempt_env.client.get(
        f"/api/attempts/{a1_id}/result",
        headers=attempt_env.student_a_headers,
    )
    assert res1.status_code == 200
    assert res1.json() == sub1_json

    # 2) show_result=True, show_correct_answers=True -> post-submission review (normalized A-D)
    exam2 = _create_and_publish_exam(
        attempt_env,
        title="Full Review Exam",
        randomize_options=True,
        show_result=True,
        show_correct_answers=True,
    )
    a2_id = attempt_env.client.post(
        f"/api/exams/{exam2['id']}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]
    deliv2 = attempt_env.client.get(
        f"/api/attempts/{a2_id}",
        headers=attempt_env.student_a_headers,
    ).json()
    sub2 = attempt_env.client.post(
        f"/api/attempts/{a2_id}/submit",
        headers=attempt_env.student_a_headers,
        json={},
    )
    assert sub2.status_code == 200
    s2 = sub2.json()
    assert s2["show_correct_answers"] is True
    assert s2["question_review"] is not None
    assert len(s2["question_review"]) == 3
    for rev_q, deliv_q in zip(s2["question_review"], deliv2["questions"], strict=True):
        assert rev_q["question_id"] == deliv_q["id"]
        assert [o["id"] for o in rev_q["options"]] == [o["id"] for o in deliv_q["options"]]
        assert [o["label"] for o in rev_q["options"]] == ["A", "B", "C", "D"]
        assert sum(1 for o in rev_q["options"] if o["is_correct"]) == 1

    # 3) show_result=False -> hides all scores & answer keys (even if DB flag flipped)
    exam3 = _create_and_publish_exam(
        attempt_env,
        title="Hidden Results Exam",
        show_result=False,
        show_correct_answers=False,
    )
    a3_id = attempt_env.client.post(
        f"/api/exams/{exam3['id']}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]
    sub3 = attempt_env.client.post(
        f"/api/attempts/{a3_id}/submit",
        headers=attempt_env.student_a_headers,
    )
    assert sub3.status_code == 200
    s3 = sub3.json()
    assert s3["status"] == "GRADED"
    assert s3["result_visible"] is False
    assert s3["show_correct_answers"] is False
    _assert_no_keys(s3, HIDDEN_SCORE_KEYS)

    with attempt_env.session_factory() as db:
        ex3_row = db.get(Exam, UUID(exam3["id"]))
        assert ex3_row is not None
        ex3_row.show_correct_answers = True
        db.commit()

    res3 = attempt_env.client.get(
        f"/api/attempts/{a3_id}/result",
        headers=attempt_env.student_a_headers,
    )
    assert res3.status_code == 200
    assert res3.json() == s3


def test_expired_attempt_delivery_and_submit_force_timer_expired(
    attempt_env: SimpleNamespace,
) -> None:
    exam = _create_and_publish_exam(attempt_env, title="Timer Enforcement", max_attempts=2)
    a1_id = attempt_env.client.post(
        f"/api/exams/{exam['id']}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]

    with attempt_env.session_factory() as db:
        att1 = db.get(ExamAttempt, UUID(a1_id))
        assert att1 is not None
        att1.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    # Expired GET delivery finalizes TIMER_EXPIRED and returns 409
    deliv_expired = attempt_env.client.get(
        f"/api/attempts/{a1_id}",
        headers=attempt_env.student_a_headers,
    )
    assert deliv_expired.status_code == 409
    assert deliv_expired.json()["code"] == "ATTEMPT_EXPIRED"
    assert deliv_expired.json()["status"] == "GRADED"

    res1 = attempt_env.client.get(
        f"/api/attempts/{a1_id}/result",
        headers=attempt_env.student_a_headers,
    )
    assert res1.status_code == 200
    assert res1.json()["submission_reason"] == "TIMER_EXPIRED"

    # Attempt #2: expired POST submit forces TIMER_EXPIRED even if confirm=False
    a2_id = attempt_env.client.post(
        f"/api/exams/{exam['id']}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]
    with attempt_env.session_factory() as db:
        att2 = db.get(ExamAttempt, UUID(a2_id))
        assert att2 is not None
        att2.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    sub2 = attempt_env.client.post(
        f"/api/attempts/{a2_id}/submit",
        headers=attempt_env.student_a_headers,
        json={"confirm": False},
    )
    assert sub2.status_code == 200
    assert sub2.json()["status"] == "GRADED"
    assert sub2.json()["submission_reason"] == "TIMER_EXPIRED"


# ---------------------------------------------------------------------------
# Student History & Admin Results Endpoints
# ---------------------------------------------------------------------------


def test_student_history_and_admin_results_summary_and_empty_state(
    attempt_env: SimpleNamespace,
) -> None:
    exam = _create_and_publish_exam(
        attempt_env,
        title="Admin Results Exam",
        pass_mark="50.00",
        max_attempts=2,
        show_result=True,
        show_correct_answers=False,
    )
    exam_id = exam["id"]

    # 0-attempt empty state
    empty_admin = attempt_env.client.get(
        f"/api/admin/exams/{exam_id}/results",
        headers=attempt_env.admin_headers,
    )
    assert empty_admin.status_code == 200
    assert empty_admin.json() == {
        "exam_id": exam_id,
        "exam_title": "Admin Results Exam",
        "pass_mark": "50.00",
        "total_attempts": 0,
        "summary": {
            "completed_attempts": 0,
            "average_percentage": None,
            "highest_percentage": None,
            "lowest_percentage": None,
            "pass_rate": None,
        },
        "attempts": [],
    }

    q1, q2, q3 = exam["questions"]

    # Student A Attempt 1: 100% (5/5)
    a1_id = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]
    for q, correct_idx in ((q1, 0), (q2, 1), (q3, 2)):
        attempt_env.client.put(
            f"/api/attempts/{a1_id}/answers/{q['id']}",
            headers=attempt_env.student_a_headers,
            json={"selected_option_id": q["options"][correct_idx]["id"]},
        )
    assert (
        attempt_env.client.post(
            f"/api/attempts/{a1_id}/submit",
            headers=attempt_env.student_a_headers,
        ).status_code
        == 200
    )

    # Student A Attempt 2: 40% (2/5 -> fail)
    a2_id = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]
    attempt_env.client.put(
        f"/api/attempts/{a2_id}/answers/{q1['id']}",
        headers=attempt_env.student_a_headers,
        json={"selected_option_id": q1["options"][0]["id"]},
    )
    assert (
        attempt_env.client.post(
            f"/api/attempts/{a2_id}/submit",
            headers=attempt_env.student_a_headers,
        ).status_code
        == 200
    )

    # Student B Attempt 1: expired unsubmitted -> 0% (lazily finalized by admin results)
    b1_id = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.student_b_headers,
    ).json()["attempt_id"]
    with attempt_env.session_factory() as db:
        b1 = db.get(ExamAttempt, UUID(b1_id))
        assert b1 is not None
        b1.expires_at = datetime.now(UTC) - timedelta(seconds=2)
        db.commit()

    # Student B Attempt 2 (via new_student): active IN_PROGRESS -> excluded from completed metrics
    c1_id = attempt_env.client.post(
        f"/api/exams/{exam_id}/attempts",
        headers=attempt_env.new_student_headers,
    ).json()["attempt_id"]

    # Hidden-result exam attempt for Student A history check
    hidden_exam = _create_and_publish_exam(
        attempt_env,
        title="Hidden History Exam",
        show_result=False,
    )
    h1_id = attempt_env.client.post(
        f"/api/exams/{hidden_exam['id']}/attempts",
        headers=attempt_env.student_a_headers,
    ).json()["attempt_id"]
    attempt_env.client.post(
        f"/api/attempts/{h1_id}/submit",
        headers=attempt_env.student_a_headers,
    )

    # Student A history shows 3 attempts; hidden_exam attempt suppresses scores
    hist_a = attempt_env.client.get(
        "/api/student/attempts",
        headers=attempt_env.student_a_headers,
    )
    assert hist_a.status_code == 200
    hist_items = hist_a.json()
    assert len(hist_items) == 3
    by_id = {item["attempt_id"]: item for item in hist_items}
    assert by_id[a1_id]["result_visible"] is True
    assert by_id[a1_id]["percentage"] == "100.00"
    assert by_id[a2_id]["percentage"] == "40.00"
    assert by_id[h1_id]["result_visible"] is False
    assert by_id[h1_id]["percentage"] is None
    assert by_id[h1_id]["points_earned"] is None
    assert by_id[h1_id]["passed"] is None

    # Admin results: 3 GRADED (100.00, 40.00, 0.00 -> avg 46.67, pass_rate 33.33), 1 IN_PROGRESS
    admin_res = attempt_env.client.get(
        f"/api/admin/exams/{exam_id}/results",
        headers=attempt_env.admin_headers,
    )
    assert admin_res.status_code == 200
    ar = admin_res.json()
    assert ar["total_attempts"] == 4
    assert ar["summary"] == {
        "completed_attempts": 3,
        "average_percentage": "46.67",
        "highest_percentage": "100.00",
        "lowest_percentage": "0.00",
        "pass_rate": "33.33",
    }
    emails = {row["attempt_id"]: row["email"] for row in ar["attempts"]}
    assert emails[a1_id] == "alice@example.edu"
    assert emails[b1_id] == "bob@example.edu"
    assert emails[c1_id] == "charlie@example.edu"

    # Admin detail on GRADED (even with show_correct_answers=False) includes question_review
    admin_detail_graded = attempt_env.client.get(
        f"/api/admin/attempts/{a1_id}",
        headers=attempt_env.admin_headers,
    )
    assert admin_detail_graded.status_code == 200
    adg = admin_detail_graded.json()
    assert adg["student_email"] == "alice@example.edu"
    assert adg["question_review"] is not None
    assert len(adg["question_review"]) == 3

    # Admin detail on hidden exam still sees full results & question breakdown
    admin_detail_hidden = attempt_env.client.get(
        f"/api/admin/attempts/{h1_id}",
        headers=attempt_env.admin_headers,
    )
    assert admin_detail_hidden.status_code == 200
    assert admin_detail_hidden.json()["question_review"] is not None

    # Admin detail on active IN_PROGRESS returns clear status and question_review=None
    admin_detail_active = attempt_env.client.get(
        f"/api/admin/attempts/{c1_id}",
        headers=attempt_env.admin_headers,
    )
    assert admin_detail_active.status_code == 200
    ada = admin_detail_active.json()
    assert ada["status"] == "IN_PROGRESS"
    assert ada["question_review"] is None


# ---------------------------------------------------------------------------
# Concurrency & Race Guard Tests
# ---------------------------------------------------------------------------


def _build_file_backed_concurrent_session_factory(
    db_path: Path,
) -> tuple[sessionmaker[Session], object]:
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        isolation_level="SERIALIZABLE",
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _begin_immediate(conn) -> None:
        # Mirrors PostgreSQL FOR UPDATE serialization across concurrent threads.
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    Base.metadata.create_all(engine)
    return (
        sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        ),
        engine,
    )


def test_concurrent_double_start_simultaneous_saves_and_save_vs_submit_races(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "concurrent_attempts.db"
    session_factory, engine = _build_file_backed_concurrent_session_factory(db_path)

    try:
        from app.exams import service as exam_service
        from app.exams.schemas import ExamCreate, QuestionCreate

        admin_id = uuid4()
        student_id = uuid4()
        with session_factory() as db:
            db.add_all(
                [
                    ApplicationUser(
                        id=admin_id,
                        auth_subject="race_admin",
                        email="race_admin@example.edu",
                        display_name="Race Admin",
                        role=ROLE_ADMIN,
                    ),
                    ApplicationUser(
                        id=student_id,
                        auth_subject="race_student",
                        email="race_student@example.edu",
                        display_name="Race Student",
                        role=ROLE_STUDENT,
                    ),
                ]
            )
            db.commit()

        admin_identity = AuthIdentity(
            subject="race_admin",
            email="race_admin@example.edu",
            name="Race Admin",
            role=ROLE_ADMIN,
            user_id=admin_id,
        )

        with session_factory() as db:
            exam = exam_service.create_exam(
                db,
                admin_identity,
                ExamCreate(
                    title="Concurrency Exam",
                    duration_minutes=30,
                    pass_mark=Decimal("50.00"),
                    max_attempts=1,
                    show_result=True,
                ),
            )
            exam_service.save_questions(
                db,
                exam.id,
                admin_identity,
                [
                    QuestionCreate.model_validate(
                        _sample_question("Race Q1", position=1, points="2.00", correct_label="A")
                    ),
                    QuestionCreate.model_validate(
                        _sample_question("Race Q2", position=2, points="2.00", correct_label="B")
                    ),
                ],
            )
            exam_service.publish_exam(db, exam.id, admin_identity)
            exam_detail = exam_service.get_exam_admin(db, exam.id, admin_identity)

        exam_id = exam_detail.id
        q1 = exam_detail.questions[0]
        q1_opt_a = q1.options[0].id
        q1_opt_b = q1.options[1].id

        # 1) 4-way concurrent double-start race -> exactly 1 attempt created, all return same ID
        start_barrier = Barrier(4)

        def _worker_start():
            start_barrier.wait(timeout=10)
            with session_factory() as db:
                return attempt_service.start_attempt(
                    db,
                    exam_id=exam_id,
                    student_user_id=student_id,
                )

        with ThreadPoolExecutor(max_workers=4) as pool:
            start_results = list(pool.map(lambda _i: _worker_start(), range(4)))

        attempt_ids = {res.attempt_id for res in start_results}
        assert len(attempt_ids) == 1
        attempt_id = next(iter(attempt_ids))
        assert sum(1 for res in start_results if not res.resumed) == 1
        assert sum(1 for res in start_results if res.resumed) == 3

        with session_factory() as db:
            rows = list(
                db.execute(
                    select(ExamAttempt).where(
                        ExamAttempt.exam_id == exam_id,
                        ExamAttempt.user_id == student_id,
                    )
                ).scalars().all()
            )
            assert len(rows) == 1

        # 2) 4-way simultaneous autosave upsert on same (attempt_id, question_id) -> zero errors
        save_barrier = Barrier(4)

        def _worker_save(opt_id: UUID):
            save_barrier.wait(timeout=10)
            with session_factory() as db:
                return attempt_service.save_answer(
                    db,
                    attempt_id=attempt_id,
                    question_id=q1.id,
                    selected_option_id=opt_id,
                    student_user_id=student_id,
                )

        with ThreadPoolExecutor(max_workers=4) as pool:
            save_results = list(
                pool.map(_worker_save, [q1_opt_a, q1_opt_b, q1_opt_a, q1_opt_b])
            )
        assert len(save_results) == 4

        with session_factory() as db:
            ans_rows = list(
                db.execute(
                    select(StudentAnswer).where(
                        StudentAnswer.attempt_id == attempt_id,
                        StudentAnswer.question_id == q1.id,
                    )
                ).scalars().all()
            )
            assert len(ans_rows) == 1
            assert ans_rows[0].selected_option_id in {q1_opt_a, q1_opt_b}

        # 3) Save vs Submit + Duplicate Submit race
        race_barrier = Barrier(4)

        def _worker_save_or_submit(idx: int):
            race_barrier.wait(timeout=10)
            with session_factory() as db:
                if idx == 0:
                    try:
                        res = attempt_service.save_answer(
                            db,
                            attempt_id=attempt_id,
                            question_id=q1.id,
                            selected_option_id=q1_opt_a,
                            student_user_id=student_id,
                        )
                        return ("save_ok", res.selected_option_id)
                    except attempt_service.AttemptConflictException as exc:
                        return ("save_409", exc.error_payload["code"])
                res = attempt_service.submit_attempt(
                    db,
                    attempt_id=attempt_id,
                    student_user_id=student_id,
                    confirm=True,
                )
                return ("submit_ok", res.percentage, res.submitted_at)

        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(_worker_save_or_submit, range(4)))

        submit_outcomes = [o for o in outcomes if o[0] == "submit_ok"]
        save_outcomes = [o for o in outcomes if o[0].startswith("save_")]
        assert len(submit_outcomes) == 3
        assert len({(o[1], o[2]) for o in submit_outcomes}) == 1
        assert len(save_outcomes) == 1

        # Verify persisted DB answer matches graded outcome consistently
        final_percentage = submit_outcomes[0][1]
        with session_factory() as db:
            persisted_attempt = db.get(ExamAttempt, attempt_id)
            persisted_answer = db.execute(
                select(StudentAnswer).where(
                    StudentAnswer.attempt_id == attempt_id,
                    StudentAnswer.question_id == q1.id,
                )
            ).scalar_one()
            assert persisted_attempt is not None
            assert persisted_attempt.status == "GRADED"
            assert persisted_attempt.percentage == final_percentage
            if persisted_answer.selected_option_id == q1_opt_a:
                assert final_percentage == Decimal("50.00")
            else:
                assert final_percentage == Decimal("0.00")
    finally:
        engine.dispose()
