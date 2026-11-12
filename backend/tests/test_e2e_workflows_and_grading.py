"""End-to-end Admin -> Student -> Admin workflow & grading precision HTTP tests.

Covers matrix case E2E-FLOW-01 through the integrated FastAPI application
(``create_app()``) with real Ed25519 JWTs, parser preview/fix, draft editing,
publication validation, randomized frozen snapshots, browser refresh/resume,
deterministic Decimal grading, admin oversight, and post-publish/closed
immutability.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.database  # noqa: F401
from app.attempts.models import ExamAttempt
from app.auth import ROLE_ADMIN
from app.auth import dependencies as auth_dependencies
from app.config import Settings
from app.database import Base
from app.database.session import get_db
from app.main import create_app
from app.users.service import upsert_application_user


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
def _build_e2e_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
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
        APP_ENV="test",
        CORS_ORIGINS=["http://localhost:5173"],
        NEON_AUTH_BASE_URL="https://auth.example.com",
        NEON_AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
        NEON_AUTH_AUDIENCE="examination-hub",
    )
    app = create_app(settings=settings)
    app.dependency_overrides[get_db] = _override_get_db

    with session_factory() as db:
        upsert_application_user(
            db,
            auth_subject="e2e-admin-sub",
            email="admin@dpcis.edu",
            display_name="Principal Examiner",
        )
        db.execute(
            text("UPDATE application_users SET role = :role WHERE auth_subject = :sub"),
            {"role": ROLE_ADMIN, "sub": "e2e-admin-sub"},
        )
        db.commit()

    admin_tok = _make_token(
        private_key, sub="e2e-admin-sub", email="admin@dpcis.edu", name="Principal Examiner"
    )
    student_a_tok = _make_token(
        private_key, sub="e2e-student-a", email="kwame@dpcis.edu", name="Kwame Mensah"
    )
    student_b_tok = _make_token(
        private_key, sub="e2e-student-b", email="ama@dpcis.edu", name="Ama Boateng"
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


def test_e2e_admin_parser_publish_student_refresh_grading_admin_oversight_and_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_e2e_env(monkeypatch) as env:
        # 1. Admin authenticates and creates DRAFT exam
        assert env.client.get("/auth/me", headers=env.admin_headers).json()["role"] == ROLE_ADMIN
        draft_resp = env.client.post(
            "/api/admin/exams",
            headers=env.admin_headers,
            json={
                "title": "Computer Science Midterm",
                "description": "Core networking and computing concepts",
                "instructions": "Select the best option for each question.",
                "duration_minutes": 45,
                "pass_mark": "60.00",
                "question_limit": 4,  # Temporarily invalid (> 3 questions after save)
                "randomize_questions": True,
                "randomize_options": True,
                "max_attempts": 2,
                "show_result": True,
                "show_correct_answers": True,
            },
        )
        assert draft_resp.status_code == 201
        exam_id = draft_resp.json()["id"]
        assert draft_resp.json()["status"] == "DRAFT"

        # 2. Admin parses dirty MCQ batch (UTF-8 BOM + CRLF + 1 invalid block) -> preview only
        dirty_raw = (
            "\ufeff1. What is the value of pi to 2 decimal places?\r\n"
            "e.g. used in geometry at 9 a.m. in C.S. class.\r\n"
            "A. 3.14\r\n"
            "B. 2.71\r\n"
            "C. 1.41\r\n"
            "D. 1.73\r\n"
            "ANSWER: A\r\n"
            "\r\n"
            "2. Broken question missing answer\r\n"
            "A. Alpha\r\n"
            "B. Beta\r\n"
            "E. Extra invalid\r\n"
        )
        dirty_parse = env.client.post(
            "/api/admin/exams/parse-questions",
            headers=env.admin_headers,
            json={"raw_text": dirty_raw},
        )
        assert dirty_parse.status_code == 200
        dp = dirty_parse.json()
        assert dp["total_blocks"] == 2
        assert dp["valid_count"] == 1
        assert dp["error_count"] >= 2
        assert dp["invalid_questions"][0]["answer_label"] is None

        # Confirm parse did NOT persist anything
        assert env.client.get(f"/api/admin/exams/{exam_id}", headers=env.admin_headers).json()[
            "questions"
        ] == []

        # 3. Admin fixes text and re-parses cleanly
        clean_raw = (
            "\ufeff1. What is the value of pi to 2 decimal places?\r\n"
            "e.g. used in geometry at 9 a.m. in C.S. class.\r\n"
            "A. 3.14\r\n"
            "B. 2.71\r\n"
            "C. 1.41\r\n"
            "D. 1.73\r\n"
            "ANSWER: A\r\n"
            "\r\n"
            "Q2: Which protocol encrypts HTTP traffic?\r\n"
            "a) FTP\r\n"
            "b) TLS\r\n"
            "c) ICMP\r\n"
            "d) ARP\r\n"
            "Correct Answer: b.\r\n"
            "\r\n"
            "3) Which data structure uses FIFO order?\r\n"
            "A. Stack\r\n"
            "B. Heap\r\n"
            "C. Queue\r\n"
            "D. Trie\r\n"
            "Ans: C\r\n"
        )
        clean_parse = env.client.post(
            "/api/admin/exams/parse-questions",
            headers=env.admin_headers,
            json={"raw_text": clean_raw},
        )
        assert clean_parse.status_code == 200
        cp = clean_parse.json()
        assert cp["valid_count"] == 3
        assert cp["error_count"] == 0

        # Convert parsed questions to save payload with weighted points (2.00, 3.00, 1.00)
        weights = ["2.00", "3.00", "1.00"]
        bulk_questions = [
            {
                "question_text": pq["question_text"],
                "position": idx,
                "points": weights[idx],
                "options": [
                    {
                        "label": opt["label"],
                        "option_text": opt["option_text"],
                        "is_correct": opt["label"] == pq["answer_label"],
                    }
                    for opt in pq["options"]
                ],
            }
            for idx, pq in enumerate(cp["valid_questions"])
        ]
        saved = env.client.put(
            f"/api/admin/exams/{exam_id}/questions",
            headers=env.admin_headers,
            json={"questions": bulk_questions},
        )
        assert saved.status_code == 200
        assert saved.json()["question_count"] == 3

        # Add a 4th question then delete it, and edit Q1 via single-question endpoints
        added_q = env.client.post(
            f"/api/admin/exams/{exam_id}/questions",
            headers=env.admin_headers,
            json={
                "question_text": "Temp question",
                "points": "1.00",
                "options": [
                    {"label": "A", "option_text": "Yes", "is_correct": True},
                    {"label": "B", "option_text": "No", "is_correct": False},
                ],
            },
        )
        assert added_q.status_code == 201
        temp_q_id = added_q.json()["id"]
        assert (
            env.client.delete(
                f"/api/admin/exams/{exam_id}/questions/{temp_q_id}",
                headers=env.admin_headers,
            ).status_code
            == 204
        )

        # 4. Publish rejected when question_limit (4) > question_count (3), then fixed & published
        bad_pub = env.client.post(
            f"/api/admin/exams/{exam_id}/publish",
            headers=env.admin_headers,
        )
        assert bad_pub.status_code == 400
        assert "question_limit" in str(bad_pub.json())

        assert (
            env.client.patch(
                f"/api/admin/exams/{exam_id}",
                headers=env.admin_headers,
                json={"question_limit": 3},
            ).status_code
            == 200
        )
        pub_resp = env.client.post(
            f"/api/admin/exams/{exam_id}/publish",
            headers=env.admin_headers,
        )
        assert pub_resp.status_code == 200
        assert pub_resp.json()["status"] == "PUBLISHED"

        admin_exam_detail = env.client.get(
            f"/api/admin/exams/{exam_id}",
            headers=env.admin_headers,
        ).json()
        correct_opt_by_qid = {
            q["id"]: next(o["id"] for o in q["options"] if o["is_correct"])
            for q in admin_exam_detail["questions"]
        }
        wrong_opt_by_qid = {
            q["id"]: next(o["id"] for o in q["options"] if not o["is_correct"])
            for q in admin_exam_detail["questions"]
        }
        points_by_qid = {q["id"]: Decimal(q["points"]) for q in admin_exam_detail["questions"]}

        # 5. Student A logs in, discovers exam, starts attempt, loads delivery
        assert env.client.get("/auth/me", headers=env.student_a_headers).json()["role"] == "STUDENT"
        student_exams = env.client.get("/api/exams", headers=env.student_a_headers).json()
        assert len(student_exams) == 1
        assert student_exams[0]["question_count"] == 3
        assert student_exams[0]["can_start"] is True

        start_a = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=env.student_a_headers,
        )
        assert start_a.status_code == 201
        att_a_id = start_a.json()["attempt_id"]

        delivery_1 = env.client.get(
            f"/api/attempts/{att_a_id}",
            headers=env.student_a_headers,
        ).json()
        assert len(delivery_1["questions"]) == 3
        # Labels in delivered snapshot must be sequential A..D regardless of shuffle
        for q in delivery_1["questions"]:
            assert [o["label"] for o in q["options"]] == ["A", "B", "C", "D"]

        q_first = delivery_1["questions"][0]["id"]
        q_second = delivery_1["questions"][1]["id"]
        q_third = delivery_1["questions"][2]["id"]

        # Save Q_first correct, Q_second wrong, Q_third selected then cleared
        assert (
            env.client.put(
                f"/api/attempts/{att_a_id}/answers/{q_first}",
                headers=env.student_a_headers,
                json={"selected_option_id": correct_opt_by_qid[q_first]},
            ).status_code
            == 200
        )
        assert (
            env.client.put(
                f"/api/attempts/{att_a_id}/answers/{q_second}",
                headers=env.student_a_headers,
                json={"selected_option_id": wrong_opt_by_qid[q_second]},
            ).status_code
            == 200
        )
        assert (
            env.client.put(
                f"/api/attempts/{att_a_id}/answers/{q_third}",
                headers=env.student_a_headers,
                json={"selected_option_id": correct_opt_by_qid[q_third]},
            ).status_code
            == 200
        )
        assert (
            env.client.put(
                f"/api/attempts/{att_a_id}/answers/{q_third}",
                headers=env.student_a_headers,
                json={"selected_option_id": None},
            ).status_code
            == 200
        )

        # 6. Simulate browser refresh: resume start returns 200 + identical frozen snapshot
        resumed_a = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=env.student_a_headers,
        )
        assert resumed_a.status_code == 200
        assert resumed_a.json()["resumed"] is True
        assert resumed_a.json()["attempt_id"] == att_a_id

        delivery_2 = env.client.get(
            f"/api/attempts/{att_a_id}",
            headers=env.student_a_headers,
        ).json()
        assert [q["id"] for q in delivery_2["questions"]] == [
            q["id"] for q in delivery_1["questions"]
        ]
        assert [[o["id"] for o in q["options"]] for q in delivery_2["questions"]] == [
            [o["id"] for o in q["options"]] for q in delivery_1["questions"]
        ]
        assert delivery_2["saved_answers"] == {
            q_first: correct_opt_by_qid[q_first],
            q_second: wrong_opt_by_qid[q_second],
            q_third: None,
        }

        # Change Q_second to correct option before submitting; Q_third stays cleared (unanswered)
        assert (
            env.client.put(
                f"/api/attempts/{att_a_id}/answers/{q_second}",
                headers=env.student_a_headers,
                json={"selected_option_id": correct_opt_by_qid[q_second]},
            ).status_code
            == 200
        )

        submit_a = env.client.post(
            f"/api/attempts/{att_a_id}/submit",
            headers=env.student_a_headers,
            json={"confirm": True},
        )
        assert submit_a.status_code == 200
        res_a = submit_a.json()
        expected_earned = points_by_qid[q_first] + points_by_qid[q_second]
        expected_avail = sum(points_by_qid.values(), Decimal("0.00"))
        expected_pct = ((expected_earned / expected_avail) * Decimal("100")).quantize(
            Decimal("0.01")
        )
        assert res_a["status"] == "GRADED"
        assert res_a["submission_reason"] == "STUDENT_SUBMITTED"
        assert res_a["correct_answers"] == 2
        assert res_a["incorrect_answers"] == 0
        assert res_a["unanswered_questions"] == 1
        assert Decimal(res_a["points_earned"]) == expected_earned
        assert Decimal(res_a["points_available"]) == expected_avail
        assert Decimal(res_a["percentage"]) == expected_pct
        assert res_a["passed"] is (expected_pct >= Decimal("60.00"))
        assert len(res_a["question_review"]) == 3

        # 7. Student B sits and times out without answering -> 0.00%
        assert env.client.get("/auth/me", headers=env.student_b_headers).json()["role"] == "STUDENT"
        att_b_id = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=env.student_b_headers,
        ).json()["attempt_id"]
        with env.session_factory() as db:
            att_b = db.get(ExamAttempt, UUID(att_b_id))
            assert att_b is not None
            att_b.expires_at = datetime.now(UTC) - timedelta(seconds=3)
            db.commit()

        # Student histories isolated strictly per student
        hist_a = env.client.get("/api/student/attempts", headers=env.student_a_headers).json()
        hist_b = env.client.get("/api/student/attempts", headers=env.student_b_headers).json()
        assert [row["attempt_id"] for row in hist_a] == [att_a_id]
        assert [row["attempt_id"] for row in hist_b] == [att_b_id]
        assert hist_b[0]["submission_reason"] == "TIMER_EXPIRED"
        assert Decimal(hist_b[0]["percentage"]) == Decimal("0.00")

        # 8. Admin sees persisted results summary & attempt details
        admin_results = env.client.get(
            f"/api/admin/exams/{exam_id}/results",
            headers=env.admin_headers,
        )
        assert admin_results.status_code == 200
        ar = admin_results.json()
        assert ar["total_attempts"] == 2
        expected_avg = (expected_pct / Decimal("2")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        expected_pass_rate = Decimal("50.00") if res_a["passed"] else Decimal("0.00")
        assert ar["summary"]["completed_attempts"] == 2
        assert Decimal(ar["summary"]["average_percentage"]) == expected_avg
        assert Decimal(ar["summary"]["highest_percentage"]) == expected_pct
        assert Decimal(ar["summary"]["lowest_percentage"]) == Decimal("0.00")
        assert Decimal(ar["summary"]["pass_rate"]) == expected_pass_rate

        admin_att_a = env.client.get(
            f"/api/admin/attempts/{att_a_id}",
            headers=env.admin_headers,
        )
        assert admin_att_a.status_code == 200
        assert admin_att_a.json()["student_email"] == "kwame@dpcis.edu"
        assert Decimal(admin_att_a.json()["percentage"]) == expected_pct

        # 9. Published exam rejects all destructive/mutating admin operations (409)
        first_qid = admin_exam_detail["questions"][0]["id"]
        assert (
            env.client.patch(
                f"/api/admin/exams/{exam_id}",
                headers=env.admin_headers,
                json={"pass_mark": "99.00"},
            ).status_code
            == 409
        )
        assert (
            env.client.put(
                f"/api/admin/exams/{exam_id}/questions",
                headers=env.admin_headers,
                json=bulk_questions,
            ).status_code
            == 409
        )
        assert (
            env.client.post(
                f"/api/admin/exams/{exam_id}/questions",
                headers=env.admin_headers,
                json=bulk_questions[0],
            ).status_code
            == 409
        )
        assert (
            env.client.put(
                f"/api/admin/exams/{exam_id}/questions/{first_qid}",
                headers=env.admin_headers,
                json=bulk_questions[0],
            ).status_code
            == 409
        )
        assert (
            env.client.delete(
                f"/api/admin/exams/{exam_id}/questions/{first_qid}",
                headers=env.admin_headers,
            ).status_code
            == 409
        )
        assert (
            env.client.delete(
                f"/api/admin/exams/{exam_id}",
                headers=env.admin_headers,
            ).status_code
            == 409
        )
        assert (
            env.client.post(
                f"/api/admin/exams/{exam_id}/publish",
                headers=env.admin_headers,
            ).status_code
            == 409
        )

        # 10. Close exam cleanly, verify idempotency & historical result preservation
        closed_1 = env.client.post(
            f"/api/admin/exams/{exam_id}/close",
            headers=env.admin_headers,
        )
        assert closed_1.status_code == 200
        assert closed_1.json()["status"] == "CLOSED"
        closed_at_1 = closed_1.json()["closed_at"]
        assert closed_at_1 is not None

        closed_2 = env.client.post(
            f"/api/admin/exams/{exam_id}/close",
            headers=env.admin_headers,
        )
        assert closed_2.status_code == 200
        assert closed_2.json()["closed_at"] == closed_at_1

        assert env.client.get("/api/exams", headers=env.student_a_headers).json() == []
        assert (
            env.client.post(
                f"/api/exams/{exam_id}/attempts",
                headers=env.student_a_headers,
            ).status_code
            == 400
        )
        # Historical results remain intact after closing
        assert (
            Decimal(
                env.client.get(
                    f"/api/attempts/{att_a_id}/result",
                    headers=env.student_a_headers,
                ).json()["percentage"]
            )
            == expected_pct
        )
        assert (
            env.client.get(
                f"/api/admin/exams/{exam_id}/results",
                headers=env.admin_headers,
            ).json()["summary"]["completed_attempts"]
            == 2
        )


def test_e2e_grading_precision_rounding_and_pass_mark_boundary_via_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _build_e2e_env(monkeypatch) as env:
        # 3 questions with 1.00 each; 2/3 -> 66.67% ROUND_HALF_UP
        exam_pass = env.client.post(
            "/api/admin/exams",
            headers=env.admin_headers,
            json={
                "title": "Boundary Pass 66.67",
                "duration_minutes": 15,
                "pass_mark": "66.67",
                "max_attempts": 1,
                "show_result": True,
            },
        ).json()
        exam_fail = env.client.post(
            "/api/admin/exams",
            headers=env.admin_headers,
            json={
                "title": "Boundary Fail 66.68",
                "duration_minutes": 15,
                "pass_mark": "66.68",
                "max_attempts": 1,
                "show_result": True,
            },
        ).json()

        three_qs = [
            {
                "question_text": f"Precision Q{i}",
                "position": i,
                "points": "1.00",
                "options": [
                    {"label": "A", "option_text": "Right", "is_correct": True},
                    {"label": "B", "option_text": "Wrong", "is_correct": False},
                ],
            }
            for i in range(3)
        ]

        results = []
        for ex in (exam_pass, exam_fail):
            assert (
                env.client.put(
                    f"/api/admin/exams/{ex['id']}/questions",
                    headers=env.admin_headers,
                    json=three_qs,
                ).status_code
                == 200
            )
            assert (
                env.client.post(
                    f"/api/admin/exams/{ex['id']}/publish",
                    headers=env.admin_headers,
                ).status_code
                == 200
            )
            att_id = env.client.post(
                f"/api/exams/{ex['id']}/attempts",
                headers=env.student_a_headers,
            ).json()["attempt_id"]
            delivery = env.client.get(
                f"/api/attempts/{att_id}",
                headers=env.student_a_headers,
            ).json()

            # Answer 2 right, 1 wrong -> 2.00 / 3.00 = 66.67%
            for idx, q in enumerate(delivery["questions"]):
                chosen = q["options"][0]["id"] if idx < 2 else q["options"][1]["id"]
                assert (
                    env.client.put(
                        f"/api/attempts/{att_id}/answers/{q['id']}",
                        headers=env.student_a_headers,
                        json={"selected_option_id": chosen},
                    ).status_code
                    == 200
                )

            sub = env.client.post(
                f"/api/attempts/{att_id}/submit",
                headers=env.student_a_headers,
            ).json()
            results.append(sub)

        assert results[0]["percentage"] == "66.67"
        assert results[0]["passed"] is True
        assert results[1]["percentage"] == "66.67"
        assert results[1]["passed"] is False
