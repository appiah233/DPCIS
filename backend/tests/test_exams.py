"""Comprehensive integration & unit tests for the examination lifecycle backend."""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import fitz
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.attempts.models import ExamAttempt
from app.auth import ROLE_ADMIN, ROLE_STUDENT, AuthIdentity
from app.auth import dependencies as auth_dependencies
from app.config import Settings
from app.database import Base
from app.database.session import get_db
from app.exams import service as exam_service
from app.exams.schemas import ExamCreate, ExamUpdate, QuestionCreate
from app.main import create_app
from app.users.models import ApplicationUser

FORBIDDEN_STUDENT_KEYS = {
    "is_correct",
    "correct_option_id",
    "answer_label",
    "questions",
    "options",
}


def _assert_no_forbidden_keys(payload: object) -> None:
    if isinstance(payload, dict):
        for key, val in payload.items():
            assert key not in FORBIDDEN_STUDENT_KEYS, f"Forbidden key leaked: {key}"
            _assert_no_forbidden_keys(val)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_forbidden_keys(item)


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


def _sample_question_payload(
    text: str = "What is 2 + 2?",
    *,
    position: int | None = None,
    points: str = "2.00",
    correct_label: str = "B",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "question_text": text,
        "points": points,
        "options": [
            {"label": "A", "option_text": "3", "is_correct": correct_label == "A"},
            {"label": "B", "option_text": "4", "is_correct": correct_label == "B"},
            {"label": "C", "option_text": "5", "is_correct": correct_label == "C"},
            {"label": "D", "option_text": "6", "is_correct": correct_label == "D"},
        ],
    }
    if position is not None:
        payload["position"] = position
    return payload


@pytest.fixture
def exam_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
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
    student_id = uuid4()
    other_student_id = uuid4()
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
                    id=student_id,
                    auth_subject="neon_student_sub",
                    email="student@example.edu",
                    display_name="Ada Student",
                    role=ROLE_STUDENT,
                ),
                ApplicationUser(
                    id=other_student_id,
                    auth_subject="neon_student_other",
                    email="other@example.edu",
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
    app.dependency_overrides[get_db] = _override_get_db

    admin_token = _make_token(private_key, sub="neon_admin_sub", email="admin@example.edu")
    # Forge an ADMIN claim in JWT for student to ensure DB role always wins.
    student_token = _make_token(
        private_key,
        sub="neon_student_sub",
        email="student@example.edu",
        extra_claims={"role": "ADMIN"},
    )
    unprovisioned_token = _make_token(private_key, sub="neon_unprovisioned_sub")

    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(
            client=client,
            session_factory=session_factory,
            admin_id=admin_id,
            student_id=student_id,
            other_student_id=other_student_id,
            admin_headers={"Authorization": f"Bearer {admin_token}"},
            student_headers={"Authorization": f"Bearer {student_token}"},
            unprovisioned_headers={"Authorization": f"Bearer {unprovisioned_token}"},
        )


def _create_draft_exam(
    env: SimpleNamespace,
    *,
    title: str = "Networks Midterm",
    duration_minutes: int = 45,
    pass_mark: Decimal = Decimal("60.00"),
    question_limit: int | None = None,
    max_attempts: int = 2,
    show_result: bool = True,
    show_correct_answers: bool = False,
) -> dict:
    resp = env.client.post(
        "/api/admin/exams",
        headers=env.admin_headers,
        json={
            "title": title,
            "description": "Core networking concepts",
            "instructions": "Answer all questions carefully.",
            "duration_minutes": duration_minutes,
            "pass_mark": str(pass_mark),
            "question_limit": question_limit,
            "randomize_questions": True,
            "randomize_options": True,
            "max_attempts": max_attempts,
            "show_result": show_result,
            "show_correct_answers": show_correct_answers,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_pdf_upload_preview_and_private_image_delivery(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    exam = _create_draft_exam(exam_env)
    fixture_dir = Path(__file__).parent / "fixtures"
    with fitz.open(fixture_dir / "atomic_structure_ms.pdf") as doc:
        key_text = doc[0].get_text()
    upload = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={
            "file": (
                "paper.pdf",
                (fixture_dir / "atomic_structure_qp.pdf").read_bytes(),
                "application/pdf",
            ),
            "answer_file": (
                "mark-scheme.pdf",
                (fixture_dir / "atomic_structure_ms.pdf").read_bytes(),
                "application/pdf",
            ),
        },
        data={"answer_key_text": key_text},
    )
    assert upload.status_code == 200, upload.text
    preview = upload.json()
    assert preview["valid_count"] == 24
    assert preview["valid_questions"][0]["answer_label"] == "B"
    source_id = preview["valid_questions"][0]["source_file_id"]
    assert (tmp_path / source_id / "answer-key.pdf").read_bytes() == (
        fixture_dir / "atomic_structure_ms.pdf"
    ).read_bytes()
    repeated = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={
            "file": (
                "same-paper.pdf",
                (fixture_dir / "atomic_structure_qp.pdf").read_bytes(),
                "application/pdf",
            )
        },
        data={"answer_key_text": key_text},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["valid_count"] == 24
    assert (
        repeated.json()["valid_questions"][0]["source_file_id"]
        == preview["valid_questions"][0]["source_file_id"]
    )
    image_url = preview["valid_questions"][3]["image_urls"][0]
    assert exam_env.client.get(image_url, headers=exam_env.student_headers).status_code == 403
    image = exam_env.client.get(image_url, headers=exam_env.admin_headers)
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")
    source_id = preview["valid_questions"][3]["source_file_id"]
    crop_path = f"/api/admin/exams/{exam['id']}/sources/{source_id}/questions/4/crops"
    invalid_crop = exam_env.client.put(
        crop_path,
        headers=exam_env.admin_headers,
        json={"regions": [{"page": 2, "bbox": [0, 100, 595, 110]}]},
    )
    assert invalid_crop.status_code == 422
    assert exam_env.client.get(image_url, headers=exam_env.admin_headers).content == image.content
    other_exam = _create_draft_exam(exam_env, title="Unrelated draft")
    wrong_owner = exam_env.client.put(
        crop_path.replace(exam["id"], other_exam["id"]),
        headers=exam_env.admin_headers,
        json={"regions": [{"page": 2, "bbox": [0, 90, 595, 220]}]},
    )
    assert wrong_owner.status_code == 404
    edited_crop = exam_env.client.put(
        crop_path,
        headers=exam_env.admin_headers,
        json={"regions": [{"page": 2, "bbox": [0, 90, 595, 220]}]},
    )
    assert edited_crop.status_code == 200, edited_crop.text
    assert edited_crop.json()["regions"][0]["bbox"][1] == 90
    assert (
        exam_env.client.get(
            edited_crop.json()["image_urls"][0], headers=exam_env.admin_headers
        ).status_code
        == 200
    )
    questions = [
        {
            "question_text": item["question_text"],
            "source_file_id": item["source_file_id"],
            "source_number": item["source_number"],
            "points": item["points"],
            "options": [
                {**option, "is_correct": option["label"] == item["answer_label"]}
                for option in item["options"]
            ],
        }
        for item in preview["valid_questions"]
    ]
    saved = exam_env.client.put(
        f"/api/admin/exams/{exam['id']}/questions",
        headers=exam_env.admin_headers,
        json={"questions": questions},
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["questions"]) == 24
    duplicate_save = exam_env.client.put(
        f"/api/admin/exams/{exam['id']}/questions",
        headers=exam_env.admin_headers,
        json={"questions": questions + questions},
    )
    assert duplicate_save.status_code == 200, duplicate_save.text
    assert len(duplicate_save.json()["questions"]) == 24
    published = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/publish", headers=exam_env.admin_headers
    )
    assert published.status_code == 200, published.text
    started = exam_env.client.post(
        f"/api/exams/{exam['id']}/attempts", headers=exam_env.student_headers
    )
    assert started.status_code == 201, started.text
    attempt_id = started.json()["attempt_id"]
    delivery = exam_env.client.get(f"/api/attempts/{attempt_id}", headers=exam_env.student_headers)
    assert delivery.status_code == 200, delivery.text
    delivered = delivery.json()
    assert len(delivered["questions"]) == 24
    assert "is_correct" not in str(delivered)
    student_image_url = delivered["questions"][0]["image_urls"][0]
    assert (
        exam_env.client.get(student_image_url, headers=exam_env.student_headers).status_code == 200
    )
    assert exam_env.client.get(student_image_url, headers=exam_env.admin_headers).status_code == 403


def test_scanned_pdf_upload_uses_ocr_fallback_flag(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.exams import router as exam_router
    from app.exams.pdf_import import PdfQuestion, PdfRegion

    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        exam_router,
        "detect_questions_with_ocr",
        lambda _doc: [
            PdfQuestion(
                number=1,
                regions=[PdfRegion(1, (0, 70, 600, 260))],
                extracted_text="OCR question one",
                options_text={"A": "", "B": ""},
            ),
            PdfQuestion(
                number=2,
                regions=[PdfRegion(1, (0, 270, 600, 460))],
                extracted_text="OCR question two",
                options_text={"A": "", "B": ""},
            ),
        ],
    )
    exam = _create_draft_exam(exam_env)
    data = (Path(__file__).parent / "fixtures" / "scanned_image_only.pdf").read_bytes()
    response = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("scan.pdf", data, "application/pdf")},
        data={"answer_key_text": "1 B\n2 A"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ocr_used"] is True
    assert payload["valid_count"] == 2
    assert all(item["pdf_confidence"] == "0.50" for item in payload["valid_questions"])


def test_crop_endpoint_adds_and_removes_page_region(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    exam = _create_draft_exam(exam_env)
    data = (Path(__file__).parent / "fixtures" / "spanning_pages.pdf").read_bytes()
    upload = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("span.pdf", data, "application/pdf")},
        data={"answer_key_text": "1 A\n2 B"},
    )
    assert upload.status_code == 200, upload.text
    question = upload.json()["valid_questions"][0]
    assert [region["page"] for region in question["image_regions"]] == [1, 2]
    endpoint = (
        f"/api/admin/exams/{exam['id']}/sources/{question['source_file_id']}/questions/1/crops"
    )
    removed = exam_env.client.put(
        endpoint,
        headers=exam_env.admin_headers,
        json={"regions": [question["image_regions"][0]]},
    )
    assert removed.status_code == 200, removed.text
    assert len(removed.json()["image_urls"]) == 1
    restored = exam_env.client.put(
        endpoint,
        headers=exam_env.admin_headers,
        json={"regions": question["image_regions"]},
    )
    assert restored.status_code == 200, restored.text
    assert len(restored.json()["image_urls"]) == 2


# ---------------------------------------------------------------------------
# RBAC & Identity Integrity
# ---------------------------------------------------------------------------


def test_unauthenticated_and_cross_role_access_rejected(exam_env: SimpleNamespace) -> None:
    created = _create_draft_exam(exam_env)
    exam_id = created["id"]
    q_resp = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/questions",
        headers=exam_env.admin_headers,
        json=_sample_question_payload(),
    )
    assert q_resp.status_code == 201
    question_id = q_resp.json()["id"]

    admin_calls = [
        ("POST", "/api/admin/exams", {"title": "X", "duration_minutes": 10, "pass_mark": 50}),
        ("GET", "/api/admin/exams", None),
        ("GET", f"/api/admin/exams/{exam_id}", None),
        ("PATCH", f"/api/admin/exams/{exam_id}", {"title": "Y"}),
        ("DELETE", f"/api/admin/exams/{exam_id}", None),
        ("POST", "/api/admin/exams/parse-questions", {"raw_text": "1. Q"}),
        ("PUT", f"/api/admin/exams/{exam_id}/questions", {"questions": []}),
        ("POST", f"/api/admin/exams/{exam_id}/questions", _sample_question_payload()),
        ("PUT", f"/api/admin/exams/{exam_id}/questions/{question_id}", _sample_question_payload()),
        ("DELETE", f"/api/admin/exams/{exam_id}/questions/{question_id}", None),
        ("POST", f"/api/admin/exams/{exam_id}/publish", None),
        ("POST", f"/api/admin/exams/{exam_id}/close", None),
    ]
    for method, path, body in admin_calls:
        unauth = exam_env.client.request(method, path, json=body)
        assert unauth.status_code == 401, f"{method} {path} should require auth"

        as_student = exam_env.client.request(
            method, path, headers=exam_env.student_headers, json=body
        )
        assert as_student.status_code == 403, f"{method} {path} must reject student"

        as_unknown = exam_env.client.request(
            method, path, headers=exam_env.unprovisioned_headers, json=body
        )
        assert as_unknown.status_code == 401, f"{method} {path} must fail closed for unknown admin"

    for path in ("/api/exams", f"/api/exams/{exam_id}"):
        assert exam_env.client.get(path).status_code == 401
        assert exam_env.client.get(path, headers=exam_env.admin_headers).status_code == 403


def test_service_fails_closed_when_identity_user_id_missing(exam_env: SimpleNamespace) -> None:
    missing_admin = AuthIdentity(subject="neon_admin_sub", email=None, name=None, role=ROLE_ADMIN)
    missing_student = AuthIdentity(
        subject="neon_student_sub", email=None, name=None, role=ROLE_STUDENT
    )

    with pytest.raises(HTTPException) as admin_exc:
        exam_service.require_admin_user_id(missing_admin)
    assert admin_exc.value.status_code == 401

    with pytest.raises(HTTPException) as student_exc:
        exam_service.require_student_user_id(missing_student)
    assert student_exc.value.status_code == 401

    with exam_env.session_factory() as db:
        with pytest.raises(HTTPException) as create_exc:
            exam_service.create_exam(
                db,
                missing_admin,
                ExamCreate(title="Fail Closed", duration_minutes=15, pass_mark=Decimal("50.00")),
            )
        assert create_exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Admin CRUD, Validation, and Question Authoring
# ---------------------------------------------------------------------------


def test_create_list_update_delete_draft_exam_and_fk_identity(
    exam_env: SimpleNamespace,
) -> None:
    created = _create_draft_exam(exam_env, title="  Cloud Security  ")
    assert created["title"] == "Cloud Security"
    assert created["status"] == "DRAFT"
    assert UUID(created["created_by"]) == exam_env.admin_id
    assert created["published_at"] is None
    assert created["closed_at"] is None
    assert created["question_count"] == 0

    list_resp = exam_env.client.get("/api/admin/exams", headers=exam_env.admin_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["id"] == created["id"]

    # Update draft fields and clear nullable fields explicitly.
    patch_resp = exam_env.client.patch(
        f"/api/admin/exams/{created['id']}",
        headers=exam_env.admin_headers,
        json={
            "title": "Cloud Security II",
            "description": None,
            "instructions": None,
            "question_limit": None,
            "pass_mark": "72.50",
        },
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["title"] == "Cloud Security II"
    assert updated["description"] is None
    assert updated["instructions"] is None
    assert updated["question_limit"] is None
    assert Decimal(updated["pass_mark"]) == Decimal("72.50")

    del_resp = exam_env.client.delete(
        f"/api/admin/exams/{created['id']}",
        headers=exam_env.admin_headers,
    )
    assert del_resp.status_code == 204
    get_deleted = exam_env.client.get(
        f"/api/admin/exams/{created['id']}",
        headers=exam_env.admin_headers,
    )
    assert get_deleted.status_code == 404


_INVALID_EXAM_CREATE_PAYLOADS: list[dict[str, object]] = [
    {"title": "   ", "duration_minutes": 30, "pass_mark": 50},
    {"title": "Valid", "duration_minutes": 0, "pass_mark": 50},
    {"title": "Valid", "duration_minutes": True, "pass_mark": 50},
    {"title": "Valid", "duration_minutes": 30, "pass_mark": -0.01},
    {"title": "Valid", "duration_minutes": 30, "pass_mark": 100.01},
    {"title": "Valid", "duration_minutes": 30, "pass_mark": "NaN"},
    {"title": "Valid", "duration_minutes": 30, "pass_mark": "Infinity"},
    {"title": "Valid", "duration_minutes": 30, "pass_mark": "not-a-number"},
    {"title": "Valid", "duration_minutes": 30, "pass_mark": True},
    {"title": "Valid", "duration_minutes": 30, "pass_mark": 50, "max_attempts": 0},
    {"title": "Valid", "duration_minutes": 30, "pass_mark": 50, "question_limit": 0},
]


@pytest.mark.parametrize("bad_payload", _INVALID_EXAM_CREATE_PAYLOADS)
def test_exam_create_schema_rejects_invalid_inputs(
    bad_payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ExamCreate.model_validate(bad_payload)


@pytest.mark.parametrize("bad_payload", _INVALID_EXAM_CREATE_PAYLOADS)
def test_create_exam_rejects_invalid_inputs(
    exam_env: SimpleNamespace,
    bad_payload: dict[str, object],
) -> None:
    resp = exam_env.client.post(
        "/api/admin/exams",
        headers=exam_env.admin_headers,
        json=bad_payload,
    )
    assert resp.status_code == 422


_INVALID_EXAM_PATCH_PAYLOADS: list[dict[str, object]] = [
    {"status": "PUBLISHED"},
    {"status": "CLOSED"},
    {"title": None},
    {"title": "   "},
    {"duration_minutes": None},
    {"pass_mark": None},
    {"pass_mark": "NaN"},
    {"randomize_questions": None},
    {"randomize_options": None},
    {"max_attempts": None},
    {"show_result": None},
    {"show_correct_answers": None},
]


@pytest.mark.parametrize("bad_patch", _INVALID_EXAM_PATCH_PAYLOADS)
def test_exam_update_schema_rejects_status_bypass_and_explicit_nulls(
    bad_patch: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ExamUpdate.model_validate(bad_patch)


@pytest.mark.parametrize("bad_patch", _INVALID_EXAM_PATCH_PAYLOADS)
def test_patch_exam_rejects_status_bypass_and_explicit_nulls(
    exam_env: SimpleNamespace,
    bad_patch: dict[str, object],
) -> None:
    created = _create_draft_exam(exam_env)
    resp = exam_env.client.patch(
        f"/api/admin/exams/{created['id']}",
        headers=exam_env.admin_headers,
        json=bad_patch,
    )
    assert resp.status_code == 422


def test_parse_questions_preview_does_not_persist(exam_env: SimpleNamespace) -> None:
    raw = (
        "1. Which layer routes IP packets?\n"
        "A. Physical\n"
        "B. Data Link\n"
        "C. Network\n"
        "D. Transport\n"
        "ANSWER: C\n"
    )
    resp = exam_env.client.post(
        "/api/admin/exams/parse-questions",
        headers=exam_env.admin_headers,
        json={"raw_text": raw},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid_count"] == 1
    assert body["error_count"] == 0
    assert body["valid_questions"][0]["answer_label"] == "C"

    list_resp = exam_env.client.get("/api/admin/exams", headers=exam_env.admin_headers)
    assert list_resp.json() == []


def test_bulk_and_single_question_crud_and_validation(exam_env: SimpleNamespace) -> None:
    created = _create_draft_exam(exam_env)
    exam_id = created["id"]

    # Bulk PUT with wrapper object, omitting positions -> sequential 0, 1.
    bulk_resp = exam_env.client.put(
        f"/api/admin/exams/{exam_id}/questions",
        headers=exam_env.admin_headers,
        json={
            "questions": [
                _sample_question_payload("First question?", correct_label="A"),
                _sample_question_payload("Second question?", correct_label="D"),
            ]
        },
    )
    assert bulk_resp.status_code == 200
    detail = bulk_resp.json()
    assert detail["question_count"] == 2
    assert [q["position"] for q in detail["questions"]] == [0, 1]
    assert [o["is_correct"] for o in detail["questions"][0]["options"]] == [
        True,
        False,
        False,
        False,
    ]
    assert [o["is_correct"] for o in detail["questions"][1]["options"]] == [
        False,
        False,
        False,
        True,
    ]

    # Single-question POST appends at position 2.
    add_resp = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/questions",
        headers=exam_env.admin_headers,
        json=_sample_question_payload("Third question?", correct_label="C"),
    )
    assert add_resp.status_code == 201
    q3 = add_resp.json()
    assert q3["position"] == 2

    # Duplicate explicit position rejected with 409.
    dup_pos_resp = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/questions",
        headers=exam_env.admin_headers,
        json=_sample_question_payload("Conflict pos?", position=1),
    )
    assert dup_pos_resp.status_code == 409

    # Single-question PUT updates text, points, and correct answer safely.
    q2_id = detail["questions"][1]["id"]
    upd_resp = exam_env.client.put(
        f"/api/admin/exams/{exam_id}/questions/{q2_id}",
        headers=exam_env.admin_headers,
        json=_sample_question_payload("Updated second question?", points="5.00", correct_label="A"),
    )
    assert upd_resp.status_code == 200
    upd_q = upd_resp.json()
    assert upd_q["question_text"] == "Updated second question?"
    assert Decimal(upd_q["points"]) == Decimal("5.00")
    assert [o["is_correct"] for o in upd_q["options"]] == [True, False, False, False]

    # Single-question DELETE compacts remaining positions cleanly to 0, 1.
    del_q_resp = exam_env.client.delete(
        f"/api/admin/exams/{exam_id}/questions/{detail['questions'][0]['id']}",
        headers=exam_env.admin_headers,
    )
    assert del_q_resp.status_code == 204

    fetched = exam_env.client.get(
        f"/api/admin/exams/{exam_id}",
        headers=exam_env.admin_headers,
    )
    assert fetched.status_code == 200
    questions = fetched.json()["questions"]
    assert [q["position"] for q in questions] == [0, 1]
    assert [q["question_text"] for q in questions] == [
        "Updated second question?",
        "Third question?",
    ]

    # Raw list payload also accepted on bulk PUT; empty [] clears questions in DRAFT.
    clear_resp = exam_env.client.put(
        f"/api/admin/exams/{exam_id}/questions",
        headers=exam_env.admin_headers,
        json=[],
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["question_count"] == 0


_INVALID_QUESTION_PAYLOADS: list[dict[str, object]] = [
    # 0 correct answers
    {
        "question_text": "No key",
        "options": [
            {"label": "A", "option_text": "One", "is_correct": False},
            {"label": "B", "option_text": "Two", "is_correct": False},
        ],
    },
    # 2 correct answers
    {
        "question_text": "Two keys",
        "options": [
            {"label": "A", "option_text": "One", "is_correct": True},
            {"label": "B", "option_text": "Two", "is_correct": True},
        ],
    },
    # Duplicate option labels
    {
        "question_text": "Dup labels",
        "options": [
            {"label": "A", "option_text": "One", "is_correct": True},
            {"label": "A", "option_text": "Two", "is_correct": False},
        ],
    },
    # Non-sequential gap labels
    {
        "question_text": "Gap labels",
        "options": [
            {"label": "A", "option_text": "One", "is_correct": True},
            {"label": "C", "option_text": "Two", "is_correct": False},
        ],
    },
    # Duplicate option text (case + whitespace folded)
    {
        "question_text": "Dup texts",
        "options": [
            {"label": "A", "option_text": "New   York", "is_correct": True},
            {"label": "B", "option_text": "new york", "is_correct": False},
        ],
    },
    # Only 1 option
    {
        "question_text": "Too few",
        "options": [{"label": "A", "option_text": "Only", "is_correct": True}],
    },
    # Blank option text
    {
        "question_text": "Blank option",
        "options": [
            {"label": "A", "option_text": "   ", "is_correct": True},
            {"label": "B", "option_text": "Valid", "is_correct": False},
        ],
    },
    # Non-positive or NaN points
    {
        "question_text": "Zero points",
        "points": "0.00",
        "options": [
            {"label": "A", "option_text": "One", "is_correct": True},
            {"label": "B", "option_text": "Two", "is_correct": False},
        ],
    },
    {
        "question_text": "NaN points",
        "points": "NaN",
        "options": [
            {"label": "A", "option_text": "One", "is_correct": True},
            {"label": "B", "option_text": "Two", "is_correct": False},
        ],
    },
]


@pytest.mark.parametrize("bad_question", _INVALID_QUESTION_PAYLOADS)
def test_question_create_schema_rejects_bad_questions(
    bad_question: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        QuestionCreate.model_validate(bad_question)


@pytest.mark.parametrize("bad_question", _INVALID_QUESTION_PAYLOADS)
def test_question_create_validation_rejects_bad_questions(
    exam_env: SimpleNamespace,
    bad_question: dict[str, object],
) -> None:
    created = _create_draft_exam(exam_env)
    resp = exam_env.client.post(
        f"/api/admin/exams/{created['id']}/questions",
        headers=exam_env.admin_headers,
        json=bad_question,
    )
    assert resp.status_code == 422


def test_bulk_save_questions_rejects_duplicate_explicit_positions(
    exam_env: SimpleNamespace,
) -> None:
    created = _create_draft_exam(exam_env)
    resp = exam_env.client.put(
        f"/api/admin/exams/{created['id']}/questions",
        headers=exam_env.admin_headers,
        json={
            "questions": [
                _sample_question_payload("Q1", position=1),
                _sample_question_payload("Q2", position=1),
            ]
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Lifecycle Transitions & Immutability Safeguards
# ---------------------------------------------------------------------------


def test_publish_validation_lifecycle_immutability_and_close(
    exam_env: SimpleNamespace,
) -> None:
    exam = _create_draft_exam(
        exam_env,
        question_limit=2,
        show_result=False,
        show_correct_answers=True,
    )
    exam_id = exam["id"]

    # Cannot close a DRAFT exam.
    close_draft = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/close",
        headers=exam_env.admin_headers,
    )
    assert close_draft.status_code == 409

    # Cannot publish with 0 questions / inconsistent show_correct_answers.
    pub_fail_empty = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/publish",
        headers=exam_env.admin_headers,
    )
    assert pub_fail_empty.status_code == 400
    errs = pub_fail_empty.json()["detail"]["errors"]
    assert "at least one question is required" in errs
    assert any("show_correct_answers" in e for e in errs)

    # Fix config & add only 1 question while question_limit == 2.
    exam_env.client.patch(
        f"/api/admin/exams/{exam_id}",
        headers=exam_env.admin_headers,
        json={"show_result": True, "show_correct_answers": True},
    )
    q1 = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/questions",
        headers=exam_env.admin_headers,
        json=_sample_question_payload("Q1?"),
    ).json()

    pub_fail_limit = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/publish",
        headers=exam_env.admin_headers,
    )
    assert pub_fail_limit.status_code == 400
    assert (
        "question_limit exceeds the number of available questions"
        in (pub_fail_limit.json()["detail"]["errors"])
    )

    # Add second question so question_limit == len(questions) (boundary passes).
    exam_env.client.post(
        f"/api/admin/exams/{exam_id}/questions",
        headers=exam_env.admin_headers,
        json=_sample_question_payload("Q2?"),
    )

    pub_ok = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/publish",
        headers=exam_env.admin_headers,
    )
    assert pub_ok.status_code == 200
    pub_body = pub_ok.json()
    assert pub_body["status"] == "PUBLISHED"
    assert pub_body["published_at"] is not None
    assert pub_body["closed_at"] is None
    assert pub_body["question_count"] == 2

    # PUBLISHED immutability: settings, questions, delete, re-publish all return 409.
    assert (
        exam_env.client.patch(
            f"/api/admin/exams/{exam_id}",
            headers=exam_env.admin_headers,
            json={"title": "Tampered"},
        ).status_code
        == 409
    )
    assert (
        exam_env.client.delete(
            f"/api/admin/exams/{exam_id}",
            headers=exam_env.admin_headers,
        ).status_code
        == 409
    )
    assert (
        exam_env.client.put(
            f"/api/admin/exams/{exam_id}/questions",
            headers=exam_env.admin_headers,
            json={"questions": [_sample_question_payload("Overwrite?")]},
        ).status_code
        == 409
    )
    assert (
        exam_env.client.post(
            f"/api/admin/exams/{exam_id}/questions",
            headers=exam_env.admin_headers,
            json=_sample_question_payload("Add?"),
        ).status_code
        == 409
    )
    assert (
        exam_env.client.put(
            f"/api/admin/exams/{exam_id}/questions/{q1['id']}",
            headers=exam_env.admin_headers,
            json=_sample_question_payload("Mutate?"),
        ).status_code
        == 409
    )
    assert (
        exam_env.client.delete(
            f"/api/admin/exams/{exam_id}/questions/{q1['id']}",
            headers=exam_env.admin_headers,
        ).status_code
        == 409
    )
    assert (
        exam_env.client.post(
            f"/api/admin/exams/{exam_id}/publish",
            headers=exam_env.admin_headers,
        ).status_code
        == 409
    )

    # Close PUBLISHED -> CLOSED, stamps closed_at.
    close_ok = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/close",
        headers=exam_env.admin_headers,
    )
    assert close_ok.status_code == 200
    closed_body = close_ok.json()
    assert closed_body["status"] == "CLOSED"
    assert closed_body["closed_at"] is not None

    # Idempotent close preserves original closed_at.
    close_again = exam_env.client.post(
        f"/api/admin/exams/{exam_id}/close",
        headers=exam_env.admin_headers,
    )
    assert close_again.status_code == 200
    assert close_again.json()["closed_at"] == closed_body["closed_at"]

    # CLOSED remains immutable.
    assert (
        exam_env.client.patch(
            f"/api/admin/exams/{exam_id}",
            headers=exam_env.admin_headers,
            json={"title": "After close"},
        ).status_code
        == 409
    )
    assert (
        exam_env.client.post(
            f"/api/admin/exams/{exam_id}/publish",
            headers=exam_env.admin_headers,
        ).status_code
        == 409
    )


# ---------------------------------------------------------------------------
# Student Discovery & Answer-Key Isolation
# ---------------------------------------------------------------------------


def test_student_views_only_published_exams_with_counts_and_zero_answer_keys(
    exam_env: SimpleNamespace,
) -> None:
    draft = _create_draft_exam(exam_env, title="Draft Hidden")
    published = _create_draft_exam(
        exam_env,
        title="Published Exam",
        question_limit=2,
        max_attempts=2,
    )
    closed = _create_draft_exam(exam_env, title="Closed Hidden")

    # Populate and publish `published` (3 questions, limit=2 -> student sees question_count=2).
    exam_env.client.put(
        f"/api/admin/exams/{published['id']}/questions",
        headers=exam_env.admin_headers,
        json={
            "questions": [
                _sample_question_payload("Q1"),
                _sample_question_payload("Q2"),
                _sample_question_payload("Q3"),
            ]
        },
    )
    assert (
        exam_env.client.post(
            f"/api/admin/exams/{published['id']}/publish",
            headers=exam_env.admin_headers,
        ).status_code
        == 200
    )

    # Populate, publish, then close `closed`.
    exam_env.client.put(
        f"/api/admin/exams/{closed['id']}/questions",
        headers=exam_env.admin_headers,
        json={"questions": [_sample_question_payload("Closed Q1")]},
    )
    assert (
        exam_env.client.post(
            f"/api/admin/exams/{closed['id']}/publish",
            headers=exam_env.admin_headers,
        ).status_code
        == 200
    )
    assert (
        exam_env.client.post(
            f"/api/admin/exams/{closed['id']}/close",
            headers=exam_env.admin_headers,
        ).status_code
        == 200
    )

    # Student sees only PUBLISHED exam, with zero answer-key exposure.
    list_resp = exam_env.client.get("/api/exams", headers=exam_env.student_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    _assert_no_forbidden_keys(items)
    assert len(items) == 1
    assert items[0]["id"] == published["id"]
    assert items[0]["question_count"] == 2
    assert items[0]["attempts_used"] == 0
    assert items[0]["active_attempt_id"] is None
    assert items[0]["can_start"] is True

    # Student detail 200 on PUBLISHED, 404 on DRAFT/CLOSED/unknown.
    detail_resp = exam_env.client.get(
        f"/api/exams/{published['id']}",
        headers=exam_env.student_headers,
    )
    assert detail_resp.status_code == 200
    _assert_no_forbidden_keys(detail_resp.json())
    assert detail_resp.json()["question_count"] == 2

    assert (
        exam_env.client.get(
            f"/api/exams/{draft['id']}",
            headers=exam_env.student_headers,
        ).status_code
        == 404
    )
    assert (
        exam_env.client.get(
            f"/api/exams/{closed['id']}",
            headers=exam_env.student_headers,
        ).status_code
        == 404
    )
    assert (
        exam_env.client.get(
            f"/api/exams/{uuid4()}",
            headers=exam_env.student_headers,
        ).status_code
        == 404
    )


def test_student_attempt_counts_active_and_expired_handling(
    exam_env: SimpleNamespace,
) -> None:
    exam = _create_draft_exam(exam_env, title="Attempt Tracking", max_attempts=1)
    exam_id = UUID(exam["id"])
    exam_env.client.post(
        f"/api/admin/exams/{exam_id}/questions",
        headers=exam_env.admin_headers,
        json=_sample_question_payload("Single Q"),
    )
    assert (
        exam_env.client.post(
            f"/api/admin/exams/{exam_id}/publish",
            headers=exam_env.admin_headers,
        ).status_code
        == 200
    )

    # Seed an expired IN_PROGRESS attempt for student + an unrelated student's active attempt.
    now = datetime.now(UTC)
    with exam_env.session_factory() as db:
        db.add(
            ExamAttempt(
                id=uuid4(),
                exam_id=exam_id,
                user_id=exam_env.student_id,
                started_at=now - timedelta(hours=2),
                expires_at=now - timedelta(hours=1),
                status="IN_PROGRESS",
                total_questions=1,
            )
        )
        db.add(
            ExamAttempt(
                id=uuid4(),
                exam_id=exam_id,
                user_id=exam_env.other_student_id,
                started_at=now,
                expires_at=now + timedelta(minutes=30),
                status="IN_PROGRESS",
                total_questions=1,
            )
        )
        db.commit()

    # Expired IN_PROGRESS attempt must NOT appear as resumable active_attempt_id,
    # and attempts_used == max_attempts (1) -> can_start is False.
    resp_expired = exam_env.client.get(f"/api/exams/{exam_id}", headers=exam_env.student_headers)
    assert resp_expired.status_code == 200
    body_expired = resp_expired.json()
    assert body_expired["attempts_used"] == 1
    assert body_expired["active_attempt_id"] is None
    assert body_expired["can_start"] is False

    # Other student has an unexpired IN_PROGRESS attempt -> active_attempt_id set, can_start True.
    with exam_env.session_factory() as db:
        other_view = exam_service.get_exam_student(db, exam_id, exam_env.other_student_id)
    assert other_view.attempts_used == 1
    assert other_view.active_attempt_id is not None
    assert other_view.can_start is True


def test_exam_mutations_acquire_row_locks_and_compile_for_postgresql(
    exam_env: SimpleNamespace,
) -> None:
    admin_identity = AuthIdentity(
        subject="neon_admin_sub",
        email="admin@example.edu",
        name="Exam Admin",
        role=ROLE_ADMIN,
        user_id=exam_env.admin_id,
    )
    created = _create_draft_exam(exam_env, title="Concurrency Lock Check")
    exam_id = UUID(created["id"])
    created_two = _create_draft_exam(exam_env, title="Delete Lock Check")
    delete_exam_id = UUID(created_two["id"])

    pg_dialect = postgresql.dialect()
    captured_exam_for_update_sql: list[str] = []

    def _capture_for_update(orm_execute_state: ORMExecuteState) -> None:
        if not orm_execute_state.is_select:
            return
        stmt = orm_execute_state.statement
        if getattr(stmt, "_for_update_arg", None) is None:
            return
        compiled = str(stmt.compile(dialect=pg_dialect))
        if "FROM exams" in compiled:
            captured_exam_for_update_sql.append(compiled)

    with exam_env.session_factory() as db:
        event.listen(db, "do_orm_execute", _capture_for_update)
        try:
            # Read-only admin fetch must NOT emit FOR UPDATE.
            exam_service.get_exam_admin(db, exam_id, admin_identity)
            assert captured_exam_for_update_sql == []

            # Every mutating Exam operation must lock the parent exams row via FOR UPDATE.
            exam_service.update_exam(
                db,
                exam_id,
                admin_identity,
                ExamUpdate(title="Concurrency Lock Check Updated"),
            )
            assert len(captured_exam_for_update_sql) == 1

            exam_service.save_questions(
                db,
                exam_id,
                admin_identity,
                [QuestionCreate.model_validate(_sample_question_payload("Q1"))],
            )
            assert len(captured_exam_for_update_sql) == 2

            added = exam_service.add_question(
                db,
                exam_id,
                admin_identity,
                QuestionCreate.model_validate(_sample_question_payload("Q2")),
            )
            assert added.position == 1
            assert len(captured_exam_for_update_sql) == 3

            exam_service.update_question(
                db,
                exam_id,
                added.id,
                admin_identity,
                QuestionCreate.model_validate(_sample_question_payload("Q2 updated")),
            )
            assert len(captured_exam_for_update_sql) == 4

            exam_service.delete_question(db, exam_id, added.id, admin_identity)
            assert len(captured_exam_for_update_sql) == 5

            exam_service.publish_exam(db, exam_id, admin_identity)
            assert len(captured_exam_for_update_sql) == 6

            exam_service.close_exam(db, exam_id, admin_identity)
            assert len(captured_exam_for_update_sql) == 7

            exam_service.delete_exam(db, delete_exam_id, admin_identity)
            assert len(captured_exam_for_update_sql) == 8

            for sql in captured_exam_for_update_sql:
                assert "FOR UPDATE" in sql
                assert "OUTER JOIN" not in sql
        finally:
            event.remove(db, "do_orm_execute", _capture_for_update)
