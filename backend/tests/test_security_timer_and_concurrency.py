"""Adversarial authoritative timer and HTTP concurrency race tests.

Covers matrix cases SEC-TIME-01..02 and SEC-CONC-01..03 against the full
integrated FastAPI application (``create_app()``) backed by file-based SQLite
configured with WAL journaling, foreign keys, ``busy_timeout``, and immediate
write transactions.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

import app.database  # noqa: F401
from app.attempts import grading as attempts_grading
from app.attempts import service as attempts_service
from app.attempts.models import ExamAttempt, StudentAnswer
from app.auth import ROLE_ADMIN
from app.auth import dependencies as auth_dependencies
from app.config import Settings
from app.database import Base
from app.database.session import get_db
from app.exams import service as exams_service
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
def _build_concurrent_http_env(
    monkeypatch: pytest.MonkeyPatch,
    db_path: Path,
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
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        isolation_level="SERIALIZABLE",
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _begin_immediate(conn) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE")

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
            auth_subject="timer-admin-sub",
            email="admin@example.edu",
            display_name="Timer Admin",
        )
        db.execute(
            text("UPDATE application_users SET role = :role WHERE auth_subject = :sub"),
            {"role": ROLE_ADMIN, "sub": "timer-admin-sub"},
        )
        db.commit()

    admin_tok = _make_token(
        private_key, sub="timer-admin-sub", email="admin@example.edu", name="Timer Admin"
    )
    student_tok = _make_token(
        private_key, sub="timer-student-sub", email="student@example.edu", name="Timer Student"
    )
    admin_headers = {"Authorization": f"Bearer {admin_tok}"}
    student_headers = {"Authorization": f"Bearer {student_tok}"}

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield SimpleNamespace(
                app=app,
                client=client,
                session_factory=session_factory,
                admin_headers=admin_headers,
                student_headers=student_headers,
                private_key=private_key,
            )
    finally:
        engine.dispose()


def _create_published_exam(
    env: SimpleNamespace,
    *,
    title: str = "Timer & Concurrency Exam",
    duration_minutes: int = 10,
    max_attempts: int = 1,
    randomize_questions: bool = False,
    randomize_options: bool = False,
) -> dict[str, object]:
    exam_resp = env.client.post(
        "/api/admin/exams",
        headers=env.admin_headers,
        json={
            "title": title,
            "duration_minutes": duration_minutes,
            "pass_mark": "50.00",
            "randomize_questions": randomize_questions,
            "randomize_options": randomize_options,
            "max_attempts": max_attempts,
            "show_result": True,
            "show_correct_answers": True,
        },
    )
    assert exam_resp.status_code == 201
    exam_id = exam_resp.json()["id"]

    questions = [
        {
            "question_text": "Q1",
            "position": 0,
            "points": "2.00",
            "options": [
                {"label": "A", "option_text": "Q1 Right", "is_correct": True},
                {"label": "B", "option_text": "Q1 Wrong", "is_correct": False},
            ],
        },
        {
            "question_text": "Q2",
            "position": 1,
            "points": "2.00",
            "options": [
                {"label": "A", "option_text": "Q2 Wrong", "is_correct": False},
                {"label": "B", "option_text": "Q2 Right", "is_correct": True},
            ],
        },
    ]
    detail_resp = env.client.put(
        f"/api/admin/exams/{exam_id}/questions",
        headers=env.admin_headers,
        json=questions,
    )
    assert detail_resp.status_code == 200
    assert (
        env.client.post(
            f"/api/admin/exams/{exam_id}/publish",
            headers=env.admin_headers,
        ).status_code
        == 200
    )
    return detail_resp.json()


def test_sec_time_01_and_02_authoritative_timer_boundaries_and_refresh_invariance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    t0 = datetime(2026, 11, 12, 12, 0, 0, tzinfo=UTC)
    clock = [t0]

    def _fake_now() -> datetime:
        return clock[0]

    monkeypatch.setattr(attempts_grading, "utc_now", _fake_now)
    monkeypatch.setattr(attempts_service, "utc_now", _fake_now)
    monkeypatch.setattr(exams_service, "_utc_now", _fake_now)

    with _build_concurrent_http_env(monkeypatch, tmp_path / "timer_http.db") as env:
        exam = _create_published_exam(
            env,
            duration_minutes=10,
            max_attempts=3,
            randomize_questions=True,
            randomize_options=True,
        )
        exam_id = exam["id"]

        # Start at t0 -> expires_at == t0 + 10m
        start_resp = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers={**env.student_headers, "Date": "Fri, 01 Jan 2099 00:00:00 GMT"},
        )
        assert start_resp.status_code == 201
        s_json = start_resp.json()
        attempt1_id = s_json["attempt_id"]
        assert datetime.fromisoformat(s_json["started_at"]) == t0
        assert datetime.fromisoformat(s_json["expires_at"]) == t0 + timedelta(minutes=10)

        delivery1 = env.client.get(
            f"/api/attempts/{attempt1_id}",
            headers=env.student_headers,
        ).json()
        q_order_1 = [q["id"] for q in delivery1["questions"]]
        opt_order_1 = [[o["id"] for o in q["options"]] for q in delivery1["questions"]]

        # Save Q1 1 millisecond before expiry (now < expires_at) -> allowed
        clock[0] = t0 + timedelta(minutes=10) - timedelta(milliseconds=1)
        q1_id = delivery1["questions"][0]["id"]
        q1_admin = next(q for q in exam["questions"] if q["id"] == q1_id)
        q1_right_id = next(o["id"] for o in q1_admin["options"] if o["is_correct"])
        assert (
            env.client.put(
                f"/api/attempts/{attempt1_id}/answers/{q1_id}",
                headers=env.student_headers,
                json={"selected_option_id": q1_right_id},
            ).status_code
            == 200
        )

        # SEC-TIME-02: Refresh/resume preserves started_at, expires_at & saved answers
        clock[0] = t0 + timedelta(minutes=5)
        resumed = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers={**env.student_headers, "X-Client-Time": "2099-01-01T00:00:00Z"},
        )
        assert resumed.status_code == 200
        assert resumed.json()["attempt_id"] == attempt1_id
        assert resumed.json()["resumed"] is True
        assert datetime.fromisoformat(resumed.json()["started_at"]) == t0
        assert datetime.fromisoformat(resumed.json()["expires_at"]) == t0 + timedelta(minutes=10)

        delivery2 = env.client.get(
            f"/api/attempts/{attempt1_id}",
            headers=env.student_headers,
        ).json()
        assert [q["id"] for q in delivery2["questions"]] == q_order_1
        assert [[o["id"] for o in q["options"]] for q in delivery2["questions"]] == opt_order_1
        assert delivery2["saved_answers"] == {q1_id: q1_right_id}

        # SEC-TIME-01: At exact boundary now == expires_at, autosave rejects 409 & auto-finalizes
        clock[0] = t0 + timedelta(minutes=10)
        q2_id = delivery1["questions"][1]["id"]
        q2_admin = next(q for q in exam["questions"] if q["id"] == q2_id)
        q2_right_id = next(o["id"] for o in q2_admin["options"] if o["is_correct"])
        late_save = env.client.put(
            f"/api/attempts/{attempt1_id}/answers/{q2_id}",
            headers=env.student_headers,
            json={"selected_option_id": q2_right_id},
        )
        assert late_save.status_code == 409
        assert late_save.json()["code"] == "ATTEMPT_EXPIRED"
        assert late_save.json()["status"] == "GRADED"

        res1 = env.client.get(
            f"/api/attempts/{attempt1_id}/result",
            headers=env.student_headers,
        ).json()
        assert res1["status"] == "GRADED"
        assert res1["submission_reason"] == "TIMER_EXPIRED"
        assert Decimal(res1["points_earned"]) == Decimal("2.00")
        assert Decimal(res1["percentage"]) == Decimal("50.00")

        # Attempt 2: expires without autosave call; GET delivery returns 409 ATTEMPT_EXPIRED
        clock[0] = t0 + timedelta(minutes=20)
        attempt2_id = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=env.student_headers,
        ).json()["attempt_id"]
        clock[0] = t0 + timedelta(minutes=30, seconds=5)
        expired_delivery = env.client.get(
            f"/api/attempts/{attempt2_id}",
            headers=env.student_headers,
        )
        assert expired_delivery.status_code == 409
        assert expired_delivery.json()["code"] == "ATTEMPT_EXPIRED"

        # Attempt 3: submit at now >= expires_at even with confirm=False forces TIMER_EXPIRED
        clock[0] = t0 + timedelta(minutes=40)
        attempt3_id = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=env.student_headers,
        ).json()["attempt_id"]
        clock[0] = t0 + timedelta(minutes=50)
        expired_submit = env.client.post(
            f"/api/attempts/{attempt3_id}/submit",
            headers=env.student_headers,
            json={"confirm": False},
        )
        assert expired_submit.status_code == 200
        assert expired_submit.json()["submission_reason"] == "TIMER_EXPIRED"

        # After max_attempts=3 exhausted, discovery shows can_start=False and start fails 409
        listing = env.client.get("/api/exams", headers=env.student_headers).json()
        assert listing[0]["attempts_used"] == 3
        assert listing[0]["active_attempt_id"] is None
        assert listing[0]["can_start"] is False
        assert (
            env.client.post(
                f"/api/exams/{exam_id}/attempts",
                headers=env.student_headers,
            ).status_code
            == 409
        )


def test_sec_conc_01_http_double_start_and_max_attempts_races(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with _build_concurrent_http_env(monkeypatch, tmp_path / "conc_start.db") as env:
        # Ensure student is provisioned via /auth/me before barrier race
        assert env.client.get("/auth/me", headers=env.student_headers).status_code == 200

        exam_one = _create_published_exam(env, title="Max1 Exam", max_attempts=1)
        exam_two = _create_published_exam(env, title="Max2 Exam", max_attempts=2)

        # A) 6-way concurrent start on max_attempts=1 -> exactly 1 row, 1x 201 + 5x 200 resumed
        barrier_a = Barrier(6)

        def _worker_start(target_exam_id: str, barrier: Barrier):
            barrier.wait(timeout=10)
            with TestClient(env.app, raise_server_exceptions=False) as tc:
                resp = tc.post(
                    f"/api/exams/{target_exam_id}/attempts",
                    headers=env.student_headers,
                )
                return resp.status_code, resp.json()

        with ThreadPoolExecutor(max_workers=6) as pool:
            res_a = list(
                pool.map(lambda _i: _worker_start(exam_one["id"], barrier_a), range(6))
            )

        statuses_a = [code for code, _body in res_a]
        assert statuses_a.count(201) == 1
        assert statuses_a.count(200) == 5
        ids_a = {body["attempt_id"] for _code, body in res_a}
        assert len(ids_a) == 1
        attempt1_id = next(iter(ids_a))

        with env.session_factory() as db:
            count_rows = (
                db.execute(
                    select(ExamAttempt).where(ExamAttempt.exam_id == UUID(exam_one["id"]))
                )
                .scalars()
                .all()
            )
            assert len(count_rows) == 1

        # B) Expire attempt 1 -> 4-way concurrent start on max_attempts=1 -> all 409, still 1 row
        with env.session_factory() as db:
            row = db.get(ExamAttempt, UUID(attempt1_id))
            assert row is not None
            row.expires_at = datetime.now(UTC) - timedelta(seconds=5)
            db.commit()

        barrier_b = Barrier(4)
        with ThreadPoolExecutor(max_workers=4) as pool:
            res_b = list(
                pool.map(lambda _i: _worker_start(exam_one["id"], barrier_b), range(4))
            )
        assert all(code == 409 for code, _body in res_b)
        with env.session_factory() as db:
            rows_b = (
                db.execute(
                    select(ExamAttempt).where(ExamAttempt.exam_id == UUID(exam_one["id"]))
                )
                .scalars()
                .all()
            )
            assert len(rows_b) == 1
            assert rows_b[0].status == "GRADED"
            assert rows_b[0].submission_reason == "TIMER_EXPIRED"

        # C) max_attempts=2 with 1 already GRADED -> 5-way concurrent start creates only #2
        first_id = env.client.post(
            f"/api/exams/{exam_two['id']}/attempts",
            headers=env.student_headers,
        ).json()["attempt_id"]
        assert (
            env.client.post(
                f"/api/attempts/{first_id}/submit",
                headers=env.student_headers,
            ).status_code
            == 200
        )

        barrier_c = Barrier(5)
        with ThreadPoolExecutor(max_workers=5) as pool:
            res_c = list(
                pool.map(lambda _i: _worker_start(exam_two["id"], barrier_c), range(5))
            )
        statuses_c = [code for code, _body in res_c]
        assert statuses_c.count(201) == 1
        assert statuses_c.count(200) == 4
        second_ids = {body["attempt_id"] for _code, body in res_c}
        assert len(second_ids) == 1
        assert next(iter(second_ids)) != first_id

        with env.session_factory() as db:
            rows_c = (
                db.execute(
                    select(ExamAttempt).where(ExamAttempt.exam_id == UUID(exam_two["id"]))
                )
                .scalars()
                .all()
            )
            assert len(rows_c) == 2


def test_sec_conc_02_and_03_http_duplicate_submit_timer_race_and_autosave_races(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with _build_concurrent_http_env(monkeypatch, tmp_path / "conc_submit_save.db") as env:
        assert env.client.get("/auth/me", headers=env.student_headers).status_code == 200

        exam = _create_published_exam(env, title="Submit Save Race Exam", max_attempts=3)
        exam_id = exam["id"]

        # 1) Simultaneous autosave upsert (6 concurrent PUTs) + Save-vs-Submit race (4 concurrent)
        attempt1_id = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=env.student_headers,
        ).json()["attempt_id"]
        q1_id = exam["questions"][0]["id"]
        q1_right = exam["questions"][0]["options"][0]["id"]
        q1_wrong = exam["questions"][0]["options"][1]["id"]

        save_barrier = Barrier(6)

        def _worker_save(opt_id: str):
            save_barrier.wait(timeout=10)
            with TestClient(env.app, raise_server_exceptions=False) as tc:
                resp = tc.put(
                    f"/api/attempts/{attempt1_id}/answers/{q1_id}",
                    headers=env.student_headers,
                    json={"selected_option_id": opt_id},
                )
                return resp.status_code, resp.json()

        with ThreadPoolExecutor(max_workers=6) as pool:
            save_res = list(
                pool.map(
                    _worker_save,
                    [q1_right, q1_wrong, q1_right, q1_wrong, q1_right, q1_wrong],
                )
            )
        assert all(code == 200 for code, _body in save_res)

        with env.session_factory() as db:
            ans_rows = (
                db.execute(
                    select(StudentAnswer).where(
                        StudentAnswer.attempt_id == UUID(attempt1_id),
                        StudentAnswer.question_id == UUID(q1_id),
                    )
                )
                .scalars()
                .all()
            )
            assert len(ans_rows) == 1

        # Save vs Submit + Duplicate Submit race
        race_barrier = Barrier(6)

        def _worker_save_or_submit(idx: int):
            race_barrier.wait(timeout=10)
            with TestClient(env.app, raise_server_exceptions=False) as tc:
                if idx < 2:
                    resp = tc.put(
                        f"/api/attempts/{attempt1_id}/answers/{q1_id}",
                        headers=env.student_headers,
                        json={"selected_option_id": q1_right},
                    )
                    return ("save", resp.status_code, resp.json())
                resp = tc.post(
                    f"/api/attempts/{attempt1_id}/submit",
                    headers=env.student_headers,
                    json={"confirm": True},
                )
                return ("submit", resp.status_code, resp.json())

        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(_worker_save_or_submit, range(6)))

        submits = [o for o in outcomes if o[0] == "submit"]
        saves = [o for o in outcomes if o[0] == "save"]
        assert all(code == 200 for _kind, code, _body in submits)
        assert all(code in {200, 409} for _kind, code, _body in saves)
        unique_submit_tuples = {
            (b["percentage"], b["submitted_at"], b["submission_reason"])
            for _, _, b in submits
        }
        assert len(unique_submit_tuples) == 1
        final_pct = Decimal(submits[0][2]["percentage"])

        with env.session_factory() as db:
            persisted_att = db.get(ExamAttempt, UUID(attempt1_id))
            persisted_ans = db.execute(
                select(StudentAnswer).where(
                    StudentAnswer.attempt_id == UUID(attempt1_id),
                    StudentAnswer.question_id == UUID(q1_id),
                )
            ).scalar_one()
            assert persisted_att is not None
            assert persisted_att.status == "GRADED"
            assert persisted_att.percentage == final_pct
            if persisted_ans.selected_option_id == UUID(q1_right):
                assert final_pct == Decimal("50.00")
            else:
                assert final_pct == Decimal("0.00")

        # 2) Timer-expiry vs Submit vs Delivery vs Late Save race
        attempt2_id = env.client.post(
            f"/api/exams/{exam_id}/attempts",
            headers=env.student_headers,
        ).json()["attempt_id"]
        with env.session_factory() as db:
            att2 = db.get(ExamAttempt, UUID(attempt2_id))
            assert att2 is not None
            att2.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()

        expiry_barrier = Barrier(4)

        def _worker_expired(idx: int):
            expiry_barrier.wait(timeout=10)
            with TestClient(env.app, raise_server_exceptions=False) as tc:
                if idx == 0:
                    r = tc.put(
                        f"/api/attempts/{attempt2_id}/answers/{q1_id}",
                        headers=env.student_headers,
                        json={"selected_option_id": q1_right},
                    )
                    return ("save", r.status_code, r.json())
                if idx == 1:
                    r = tc.get(
                        f"/api/attempts/{attempt2_id}",
                        headers=env.student_headers,
                    )
                    return ("deliver", r.status_code, r.json())
                r = tc.post(
                    f"/api/attempts/{attempt2_id}/submit",
                    headers=env.student_headers,
                )
                return ("submit", r.status_code, r.json())

        with ThreadPoolExecutor(max_workers=4) as pool:
            exp_outcomes = list(pool.map(_worker_expired, range(4)))

        by_kind = {kind: (code, body) for kind, code, body in exp_outcomes}
        assert by_kind["save"][0] == 409
        assert by_kind["deliver"][0] == 409
        exp_submits = [o for o in exp_outcomes if o[0] == "submit"]
        assert len(exp_submits) == 2
        for _kind, code, body in exp_submits:
            assert code == 200
            assert body["submission_reason"] == "TIMER_EXPIRED"
            assert body["percentage"] == "0.00"
            assert body["points_earned"] == "0.00"
