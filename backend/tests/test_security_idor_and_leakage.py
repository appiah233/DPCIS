"""Adversarial answer-key isolation, score security, IDOR, and leakage tests.

Covers matrix cases SEC-KEY-01..02, SEC-IDOR-01..02, SEC-SCORE-01..02, and
SEC-LEAK-01 against the full integrated FastAPI application (``create_app()``).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.database  # noqa: F401
from app.attempts.models import ExamAttempt, StudentAnswer
from app.auth import ROLE_ADMIN
from app.auth import dependencies as auth_dependencies
from app.config import Settings
from app.database import Base
from app.database.session import get_db
from app.main import create_app
from app.users.service import upsert_application_user

ACTIVE_DELIVERY_FORBIDDEN_KEYS = {
    "is_correct",
    "correct_option_id",
    "correct_answer",
    "answer_label",
    "answer_key",
    "question_review",
    "correct_answers",
    "incorrect_answers",
    "unanswered_questions",
    "points_earned",
    "points_available",
    "percentage",
    "passed",
    "pass_mark",
}

DISCOVERY_FORBIDDEN_KEYS = {
    "is_correct",
    "correct_option_id",
    "correct_answer",
    "answer_label",
    "answer_key",
    "show_correct_answers",
    "questions",
    "options",
}

HIDDEN_RESULT_FORBIDDEN_KEYS = {
    "is_correct",
    "correct_option_id",
    "correct_answer",
    "answer_label",
    "answer_key",
    "question_review",
    "correct_answers",
    "incorrect_answers",
    "unanswered_questions",
    "points_earned",
    "points_available",
    "percentage",
    "pass_mark",
    "passed",
}

NO_KEY_RESULT_FORBIDDEN_KEYS = {
    "is_correct",
    "correct_option_id",
    "correct_answer",
    "answer_label",
    "answer_key",
}


def _assert_no_keys(payload: object, forbidden: set[str], *, context: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert key not in forbidden, f"[{context}] Forbidden key leaked: {key!r}"
            _assert_no_keys(value, forbidden, context=context)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_keys(item, forbidden, context=context)


def _assert_security_headers(response, *, expected_request_id: str | None = None) -> None:
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("X-Request-ID")
    if expected_request_id is not None:
        assert response.headers.get("X-Request-ID") == expected_request_id


def _make_token(
    private_key: Ed25519PrivateKey,
    *,
    sub: str,
    email: str,
    name: str,
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "email": email,
            "name": name,
            "iss": "https://auth.example.com",
            "aud": "examination-hub",
            "exp": now + 600,
        },
        private_key,
        algorithm="EdDSA",
    )


@contextmanager
def _build_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    app_env: str = "test",
) -> Iterator[SimpleNamespace]:
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

    settings = Settings(
        _env_file=None,
        APP_ENV=app_env,
        CORS_ORIGINS=["https://exams.example.com"]
        if app_env == "production"
        else ["http://localhost:5173"],
        DATABASE_URL="postgresql://placeholder:placeholder@ep-demo.neon.tech/neondb?sslmode=require",
        NEON_AUTH_BASE_URL="https://auth.example.com",
        NEON_AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
        NEON_AUTH_AUDIENCE="examination-hub",
    )

    app = create_app(settings=settings)
    app.dependency_overrides[get_db] = _override_get_db

    boom_router = APIRouter()

    @boom_router.get("/__probe/boom")
    def _trigger_boom() -> dict[str, str]:
        raise RuntimeError(
            "postgresql://neondb_owner:super_secret_pw@ep-secret.neon.tech/neondb"
        )

    app.include_router(boom_router)

    with session_factory() as db:
        upsert_application_user(
            db,
            auth_subject="admin-sub-1",
            email="admin@example.edu",
            display_name="Chief Admin",
        )
        db.execute(
            text("UPDATE application_users SET role = :role WHERE auth_subject = :sub"),
            {"role": ROLE_ADMIN, "sub": "admin-sub-1"},
        )
        db.commit()

    admin_tok = _make_token(
        private_key, sub="admin-sub-1", email="admin@example.edu", name="Chief Admin"
    )
    student_a_tok = _make_token(
        private_key, sub="student-a-sub", email="alice@example.edu", name="Alice"
    )
    student_b_tok = _make_token(
        private_key, sub="student-b-sub", email="bob@example.edu", name="Bob"
    )
    admin_headers = {"Authorization": f"Bearer {admin_tok}"}
    student_a_headers = {"Authorization": f"Bearer {student_a_tok}"}
    student_b_headers = {"Authorization": f"Bearer {student_b_tok}"}

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield SimpleNamespace(
                client=client,
                session_factory=session_factory,
                admin_headers=admin_headers,
                student_a_headers=student_a_headers,
                student_b_headers=student_b_headers,
            )
    finally:
        engine.dispose()


def _create_exam_with_two_questions(
    env: SimpleNamespace,
    *,
    title: str,
    show_result: bool,
    show_correct_answers: bool,
    question_limit: int | None = None,
    publish: bool = True,
) -> dict[str, object]:
    create_resp = env.client.post(
        "/api/admin/exams",
        headers=env.admin_headers,
        json={
            "title": title,
            "duration_minutes": 30,
            "pass_mark": "50.00",
            "question_limit": question_limit,
            "randomize_questions": False,
            "randomize_options": False,
            "max_attempts": 3,
            "show_result": show_result,
            "show_correct_answers": show_correct_answers,
        },
    )
    assert create_resp.status_code == 201
    exam_id = create_resp.json()["id"]

    questions_payload = [
        {
            "question_text": f"{title} Q1",
            "position": 0,
            "points": "2.00",
            "options": [
                {"label": "A", "option_text": "Q1 Wrong", "is_correct": False},
                {"label": "B", "option_text": "Q1 Right", "is_correct": True},
                {"label": "C", "option_text": "Q1 Alt", "is_correct": False},
            ],
        },
        {
            "question_text": f"{title} Q2",
            "position": 1,
            "points": "2.00",
            "options": [
                {"label": "A", "option_text": "Q2 Right", "is_correct": True},
                {"label": "B", "option_text": "Q2 Wrong", "is_correct": False},
                {"label": "C", "option_text": "Q2 Alt", "is_correct": False},
            ],
        },
    ]
    save_resp = env.client.put(
        f"/api/admin/exams/{exam_id}/questions",
        headers=env.admin_headers,
        json=questions_payload,
    )
    assert save_resp.status_code == 200
    detail = save_resp.json()

    if publish:
        pub_resp = env.client.post(
            f"/api/admin/exams/{exam_id}/publish",
            headers=env.admin_headers,
        )
        assert pub_resp.status_code == 200
    return detail


def test_sec_key_01_recursive_answer_key_isolation_across_all_student_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_env(monkeypatch) as env:
        # 1. Key-enabled exam (show_result=True, show_correct_answers=True):
        #    MUST still hide all keys before GRADED.
        exam_with_review = _create_exam_with_two_questions(
            env,
            title="Key Review Exam",
            show_result=True,
            show_correct_answers=True,
        )
        # 2. Score-only exam (show_result=True, show_correct_answers=False):
        #    MUST hide all keys before AND after GRADED.
        exam_no_review = _create_exam_with_two_questions(
            env,
            title="Score Only Exam",
            show_result=True,
            show_correct_answers=False,
        )
        # 3. Hidden-result exam (show_result=False, show_correct_answers=False):
        #    MUST hide scores AND keys after GRADED.
        exam_hidden = _create_exam_with_two_questions(
            env,
            title="Hidden Result Exam",
            show_result=False,
            show_correct_answers=False,
        )

        # Discovery endpoints never expose questions/options/keys
        list_resp = env.client.get("/api/exams", headers=env.student_a_headers)
        assert list_resp.status_code == 200
        _assert_security_headers(list_resp)
        _assert_no_keys(list_resp.json(), DISCOVERY_FORBIDDEN_KEYS, context="GET /api/exams")

        for ex in (exam_with_review, exam_no_review, exam_hidden):
            ex_id = ex["id"]
            detail_resp = env.client.get(f"/api/exams/{ex_id}", headers=env.student_a_headers)
            assert detail_resp.status_code == 200
            _assert_no_keys(
                detail_resp.json(), DISCOVERY_FORBIDDEN_KEYS, context="GET /api/exams/{id}"
            )

            start_resp = env.client.post(
                f"/api/exams/{ex_id}/attempts",
                headers=env.student_a_headers,
            )
            assert start_resp.status_code == 201
            attempt_id = start_resp.json()["attempt_id"]
            _assert_no_keys(
                start_resp.json(),
                ACTIVE_DELIVERY_FORBIDDEN_KEYS,
                context="POST /api/exams/{id}/attempts",
            )

            delivery_resp = env.client.get(
                f"/api/attempts/{attempt_id}",
                headers=env.student_a_headers,
            )
            assert delivery_resp.status_code == 200
            delivery_json = delivery_resp.json()
            _assert_no_keys(
                delivery_json, ACTIVE_DELIVERY_FORBIDDEN_KEYS, context="GET /api/attempts/{id}"
            )

            q1 = delivery_json["questions"][0]
            save_resp = env.client.put(
                f"/api/attempts/{attempt_id}/answers/{q1['id']}",
                headers=env.student_a_headers,
                json={"selected_option_id": q1["options"][1]["id"]},
            )
            assert save_resp.status_code == 200
            _assert_no_keys(
                save_resp.json(),
                ACTIVE_DELIVERY_FORBIDDEN_KEYS,
                context="PUT /api/attempts/{id}/answers/{qid}",
            )

            # Result endpoint blocked while IN_PROGRESS
            premature_res = env.client.get(
                f"/api/attempts/{attempt_id}/result",
                headers=env.student_a_headers,
            )
            assert premature_res.status_code == 409
            _assert_no_keys(
                premature_res.json(),
                ACTIVE_DELIVERY_FORBIDDEN_KEYS,
                context="GET /api/attempts/{id}/result (active)",
            )

            # History while IN_PROGRESS hides scores/keys
            hist_active = env.client.get("/api/student/attempts", headers=env.student_a_headers)
            assert hist_active.status_code == 200
            _assert_no_keys(
                hist_active.json(),
                NO_KEY_RESULT_FORBIDDEN_KEYS,
                context="GET /api/student/attempts (active)",
            )
            for item in hist_active.json():
                if item["attempt_id"] == attempt_id:
                    assert item["result_visible"] is False
                    assert item["percentage"] is None
                    assert item["points_earned"] is None
                    assert item["passed"] is None

            # Submit and inspect disclosure per exam policy
            submit_resp = env.client.post(
                f"/api/attempts/{attempt_id}/submit",
                headers=env.student_a_headers,
            )
            assert submit_resp.status_code == 200
            result_resp = env.client.get(
                f"/api/attempts/{attempt_id}/result",
                headers=env.student_a_headers,
            )
            assert result_resp.status_code == 200

            if ex is exam_hidden:
                for payload in (submit_resp.json(), result_resp.json()):
                    assert payload["result_visible"] is False
                    assert payload["show_correct_answers"] is False
                    _assert_no_keys(
                        payload, HIDDEN_RESULT_FORBIDDEN_KEYS, context="hidden result"
                    )
            elif ex is exam_no_review:
                for payload in (submit_resp.json(), result_resp.json()):
                    assert payload["result_visible"] is True
                    assert payload["show_correct_answers"] is False
                    assert payload["question_review"] is None
                    _assert_no_keys(
                        payload, NO_KEY_RESULT_FORBIDDEN_KEYS, context="score-only result"
                    )
            else:
                for payload in (submit_resp.json(), result_resp.json()):
                    assert payload["result_visible"] is True
                    assert payload["show_correct_answers"] is True
                    assert isinstance(payload["question_review"], list)
                    assert len(payload["question_review"]) == 2

        # History post-grading still withholds hidden-exam scores
        hist_after = env.client.get("/api/student/attempts", headers=env.student_a_headers)
        assert hist_after.status_code == 200
        _assert_no_keys(
            hist_after.json(),
            NO_KEY_RESULT_FORBIDDEN_KEYS,
            context="GET /api/student/attempts (graded)",
        )
        by_title = {item["exam_title"]: item for item in hist_after.json()}
        assert by_title["Hidden Result Exam"]["result_visible"] is False
        assert by_title["Hidden Result Exam"]["percentage"] is None
        assert by_title["Hidden Result Exam"]["passed"] is None


def test_sec_key_02_draft_and_closed_exams_are_inaccessible_to_students(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_env(monkeypatch) as env:
        draft = _create_exam_with_two_questions(
            env,
            title="Secret Draft Exam",
            show_result=True,
            show_correct_answers=True,
            publish=False,
        )
        closed = _create_exam_with_two_questions(
            env,
            title="Closed Exam",
            show_result=True,
            show_correct_answers=True,
            publish=True,
        )
        close_resp = env.client.post(
            f"/api/admin/exams/{closed['id']}/close",
            headers=env.admin_headers,
        )
        assert close_resp.status_code == 200

        listing = env.client.get("/api/exams", headers=env.student_a_headers)
        assert listing.status_code == 200
        assert listing.json() == []

        for non_public_id, expected_start_status in (
            (draft["id"], 404),
            (closed["id"], 400),
        ):
            detail = env.client.get(
                f"/api/exams/{non_public_id}",
                headers=env.student_a_headers,
            )
            assert detail.status_code == 404
            _assert_no_keys(detail.json(), DISCOVERY_FORBIDDEN_KEYS, context="non-public exam")

            start = env.client.post(
                f"/api/exams/{non_public_id}/attempts",
                headers=env.student_a_headers,
            )
            assert start.status_code == expected_start_status
            _assert_no_keys(start.json(), DISCOVERY_FORBIDDEN_KEYS, context="start non-public")


def test_sec_score_01_and_02_client_tampering_rejected_and_graded_scores_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_env(monkeypatch) as env:
        exam = _create_exam_with_two_questions(
            env,
            title="Tamper Proof Exam",
            show_result=True,
            show_correct_answers=False,
        )
        exam_id = exam["id"]

        # Reject tampered start payload fields
        for bad_start in (
            {"expires_at": "2099-01-01T00:00:00Z"},
            {"started_at": "2000-01-01T00:00:00Z"},
            {"status": "GRADED"},
            {"percentage": 100},
            {"user_id": str(uuid4())},
        ):
            resp = env.client.post(
                f"/api/exams/{exam_id}/attempts",
                headers=env.student_a_headers,
                json=bad_start,
            )
            assert resp.status_code == 422

        attempt_id = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=env.student_a_headers,
        ).json()["attempt_id"]
        delivery = env.client.get(
            f"/api/attempts/{attempt_id}",
            headers=env.student_a_headers,
        ).json()
        q1 = delivery["questions"][0]
        wrong_opt_id = q1["options"][0]["id"]  # Option A is incorrect

        # Reject tampered autosave payload fields
        for bad_save in (
            {"selected_option_id": wrong_opt_id, "is_correct": True},
            {"selected_option_id": wrong_opt_id, "points_earned": "99.00"},
            {"selected_option_id": wrong_opt_id, "percentage": "100.00"},
        ):
            resp = env.client.put(
                f"/api/attempts/{attempt_id}/answers/{q1['id']}",
                headers=env.student_a_headers,
                json=bad_save,
            )
            assert resp.status_code == 422

        # Save wrong option legitimately
        assert (
            env.client.put(
                f"/api/attempts/{attempt_id}/answers/{q1['id']}",
                headers=env.student_a_headers,
                json={"selected_option_id": wrong_opt_id},
            ).status_code
            == 200
        )

        # Reject tampered submit payload fields
        for bad_submit in (
            {"confirm": True, "score": 100},
            {"confirm": True, "percentage": "100.00"},
            {"confirm": True, "passed": True},
            {"confirm": True, "points_earned": "4.00"},
            {"confirm": True, "correct_answers": 2},
            {"confirm": True, "status": "GRADED"},
        ):
            resp = env.client.post(
                f"/api/attempts/{attempt_id}/submit",
                headers=env.student_a_headers,
                json=bad_submit,
            )
            assert resp.status_code == 422

        # Legitimate submit computes 0.00% on server
        submitted = env.client.post(
            f"/api/attempts/{attempt_id}/submit",
            headers=env.student_a_headers,
            json={"confirm": True},
        )
        assert submitted.status_code == 200
        s_json = submitted.json()
        assert s_json["points_earned"] == "0.00"
        assert s_json["points_available"] == "4.00"
        assert s_json["percentage"] == "0.00"
        assert s_json["passed"] is False
        original_submitted_at = s_json["submitted_at"]

        # Post-GRADED immutability: mutations and delivery rejected 409
        assert (
            env.client.put(
                f"/api/attempts/{attempt_id}/answers/{q1['id']}",
                headers=env.student_a_headers,
                json={"selected_option_id": q1["options"][1]["id"]},
            ).status_code
            == 409
        )
        assert (
            env.client.get(
                f"/api/attempts/{attempt_id}",
                headers=env.student_a_headers,
            ).status_code
            == 409
        )

        # Even if DB question/option rows changed out-of-band after grading,
        # persisted attempt scores remain strictly immutable on re-submit/get.
        with env.session_factory() as db:
            db.execute(
                text("UPDATE questions SET points = 50.00 WHERE id = :qid"),
                {"qid": UUID(q1["id"]).hex},
            )
            db.execute(
                text("UPDATE question_options SET is_correct = 0 WHERE question_id = :qid"),
                {"qid": UUID(q1["id"]).hex},
            )
            db.execute(
                text("UPDATE question_options SET is_correct = 1 WHERE id = :oid"),
                {"oid": UUID(wrong_opt_id).hex},
            )
            db.commit()

        resubmit = env.client.post(
            f"/api/attempts/{attempt_id}/submit",
            headers=env.student_a_headers,
            json={"confirm": True},
        )
        assert resubmit.status_code == 200
        r_json = resubmit.json()
        assert r_json["points_earned"] == "0.00"
        assert r_json["points_available"] == "4.00"
        assert r_json["percentage"] == "0.00"
        assert r_json["passed"] is False
        assert r_json["submitted_at"] == original_submitted_at

        fetched = env.client.get(
            f"/api/attempts/{attempt_id}/result",
            headers=env.student_a_headers,
        )
        assert fetched.status_code == 200
        assert fetched.json()["percentage"] == "0.00"
        assert fetched.json()["points_earned"] == "0.00"


def test_sec_idor_01_and_02_cross_student_attempt_and_cross_exam_injection_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_env(monkeypatch) as env:
        # Exam 1 has 2 questions, question_limit=1 (so 1 question is outside Attempt 1's snapshot)
        exam1 = _create_exam_with_two_questions(
            env,
            title="IDOR Exam 1",
            show_result=True,
            show_correct_answers=True,
            question_limit=1,
        )
        exam2 = _create_exam_with_two_questions(
            env,
            title="IDOR Exam 2",
            show_result=True,
            show_correct_answers=True,
        )

        # Student A starts Exam 1 and saves the correct answer
        a_attempt_id = env.client.post(
            f"/api/exams/{exam1['id']}/attempts",
            headers=env.student_a_headers,
        ).json()["attempt_id"]
        a_delivery = env.client.get(
            f"/api/attempts/{a_attempt_id}",
            headers=env.student_a_headers,
        ).json()
        selected_q = a_delivery["questions"][0]
        selected_q_id = selected_q["id"]
        # Find correct option from admin payload
        admin_q_match = next(q for q in exam1["questions"] if q["id"] == selected_q_id)
        correct_opt_id = next(o["id"] for o in admin_q_match["options"] if o["is_correct"])
        wrong_opt_id = next(o["id"] for o in admin_q_match["options"] if not o["is_correct"])

        assert (
            env.client.put(
                f"/api/attempts/{a_attempt_id}/answers/{selected_q_id}",
                headers=env.student_a_headers,
                json={"selected_option_id": correct_opt_id},
            ).status_code
            == 200
        )

        # Student B cannot read, mutate, submit, or view Student A's attempt
        assert (
            env.client.get(
                f"/api/attempts/{a_attempt_id}",
                headers=env.student_b_headers,
            ).status_code
            == 404
        )
        assert (
            env.client.put(
                f"/api/attempts/{a_attempt_id}/answers/{selected_q_id}",
                headers=env.student_b_headers,
                json={"selected_option_id": wrong_opt_id},
            ).status_code
            == 404
        )
        assert (
            env.client.put(
                f"/api/attempts/{a_attempt_id}/answers/{selected_q_id}",
                headers=env.student_b_headers,
                json={"selected_option_id": None},
            ).status_code
            == 404
        )
        assert (
            env.client.post(
                f"/api/attempts/{a_attempt_id}/submit",
                headers=env.student_b_headers,
                json={"confirm": True},
            ).status_code
            == 404
        )
        assert (
            env.client.get(
                f"/api/attempts/{a_attempt_id}/result",
                headers=env.student_b_headers,
            ).status_code
            == 404
        )
        b_history = env.client.get("/api/student/attempts", headers=env.student_b_headers)
        assert b_history.status_code == 200
        assert b_history.json() == []

        # Student A's attempt must still be IN_PROGRESS with original answer preserved
        with env.session_factory() as db:
            att = db.get(ExamAttempt, UUID(a_attempt_id))
            assert att is not None
            assert att.status == "IN_PROGRESS"
            ans = db.execute(
                select(StudentAnswer).where(
                    StudentAnswer.attempt_id == UUID(a_attempt_id),
                    StudentAnswer.question_id == UUID(selected_q_id),
                )
            ).scalar_one()
            assert ans.selected_option_id == UUID(correct_opt_id)

        # SEC-IDOR-02: Student A cannot inject question from Exam 2, unselected question from
        # Exam 1, option from another question, or nonexistent option UUID.
        unselected_q = next(q for q in exam1["questions"] if q["id"] != selected_q_id)
        exam2_q = exam2["questions"][0]

        for bad_qid, bad_oid in (
            (exam2_q["id"], exam2_q["options"][0]["id"]),
            (unselected_q["id"], unselected_q["options"][0]["id"]),
            (selected_q_id, unselected_q["options"][0]["id"]),
            (selected_q_id, exam2_q["options"][0]["id"]),
            (selected_q_id, str(uuid4())),
            (str(uuid4()), correct_opt_id),
        ):
            resp = env.client.put(
                f"/api/attempts/{a_attempt_id}/answers/{bad_qid}",
                headers=env.student_a_headers,
                json={"selected_option_id": bad_oid},
            )
            assert resp.status_code == 400

        # Submit Student A legitimately -> still 100.00%
        submit_a = env.client.post(
            f"/api/attempts/{a_attempt_id}/submit",
            headers=env.student_a_headers,
        )
        assert submit_a.status_code == 200
        assert Decimal(submit_a.json()["percentage"]) == Decimal("100.00")

        # Student B still blocked from reading Student A's graded result
        assert (
            env.client.get(
                f"/api/attempts/{a_attempt_id}/result",
                headers=env.student_b_headers,
            ).status_code
            == 404
        )


def test_sec_leak_01_security_headers_error_masking_and_production_hardening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_env(monkeypatch, app_env="production") as env:
        # Docs / OpenAPI disabled in production
        for doc_path in ("/docs", "/redoc", "/openapi.json"):
            doc_resp = env.client.get(doc_path)
            assert doc_resp.status_code == 404
            _assert_security_headers(doc_resp)

        # Validation error in production masks field internals behind request_id
        val_resp = env.client.post(
            "/api/admin/exams",
            headers={**env.admin_headers, "X-Request-ID": "req-prod-val-1"},
            json={"title": "", "duration_minutes": -5},
        )
        assert val_resp.status_code == 422
        _assert_security_headers(val_resp, expected_request_id="req-prod-val-1")
        assert val_resp.json() == {
            "detail": "Invalid request payload",
            "request_id": "req-prod-val-1",
        }

        # Unhandled 500 masks secret DB strings & stack traces behind request_id
        # while retaining security headers and CORS headers for allowed origins.
        boom_resp = env.client.get(
            "/__probe/boom",
            headers={
                "X-Request-ID": "req-prod-boom-9",
                "Origin": "https://exams.example.com",
            },
        )
        assert boom_resp.status_code == 500
        _assert_security_headers(boom_resp, expected_request_id="req-prod-boom-9")
        assert (
            boom_resp.headers.get("access-control-allow-origin")
            == "https://exams.example.com"
        )
        assert boom_resp.json() == {
            "detail": "Internal server error",
            "request_id": "req-prod-boom-9",
        }
        lowered = boom_resp.text.lower()
        for forbidden in (
            "super_secret_pw",
            "neondb_owner",
            "neon.tech",
            "traceback",
            "runtimeerror",
        ):
            assert forbidden not in lowered

        # Disallowed origin on 500 does not get CORS reflection, still keeps security headers
        evil_boom = env.client.get(
            "/__probe/boom",
            headers={
                "X-Request-ID": "req-prod-boom-evil",
                "Origin": "https://evil.example.net",
            },
        )
        assert evil_boom.status_code == 500
        _assert_security_headers(evil_boom, expected_request_id="req-prod-boom-evil")
        assert evil_boom.headers.get("access-control-allow-origin") is None

        # Verify security headers also appear on 401, 403, 404, 409 responses
        unauth_resp = env.client.get("/api/exams")
        assert unauth_resp.status_code == 401
        _assert_security_headers(unauth_resp)

        # Provision student_a first so admin-route check triggers 403 (role check) not 401
        assert (
            env.client.get("/auth/me", headers=env.student_a_headers).status_code == 200
        )
        forbidden_resp = env.client.get("/api/admin/exams", headers=env.student_a_headers)
        assert forbidden_resp.status_code == 403
        _assert_security_headers(forbidden_resp)

        not_found_resp = env.client.get(
            f"/api/exams/{uuid4()}", headers=env.student_a_headers
        )
        assert not_found_resp.status_code == 404
        _assert_security_headers(not_found_resp)

        exam = _create_exam_with_two_questions(
            env,
            title="Header Conflict Exam",
            show_result=True,
            show_correct_answers=False,
        )
        att_id = env.client.post(
            f"/api/exams/{exam['id']}/attempts",
            headers=env.student_a_headers,
        ).json()["attempt_id"]
        conflict_resp = env.client.get(
            f"/api/attempts/{att_id}/result",
            headers=env.student_a_headers,
        )
        assert conflict_resp.status_code == 409
        _assert_security_headers(conflict_resp)
