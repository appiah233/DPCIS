"""Comprehensive tests for screenshot-based PDF import, page rendering, crops, and security."""
# ruff: noqa: F811

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from alembic import command
from alembic.config import Config
from tests.test_exams import exam_env  # noqa: F401

from app.exams.pdf_storage import source_dir


def _build_pdf(
    pages: list[list[tuple[tuple[float, float], str]]],
    *,
    width: float = 595.0,
    height: float = 842.0,
    draw_diagram: bool = False,
    draw_table: bool = False,
    encrypt: bool = False,
) -> bytes:
    doc = fitz.open()
    for page_items in pages:
        page = doc.new_page(width=width, height=height)
        for (x, y), text in page_items:
            page.insert_text((x, y), text, fontsize=11)
        if draw_diagram:
            page.draw_rect(fitz.Rect(72, 130, 260, 210), color=(0, 0, 0), width=1.5)
            page.draw_circle((166, 170), 25, color=(0, 0, 0), width=1.5)
        if draw_table:
            for r in range(3):
                page.draw_rect(fitz.Rect(72, 130 + r * 20, 250, 150 + r * 20), color=(0, 0, 0))
    if encrypt:
        return doc.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner123",
            user_pw="user123",
        )
    return doc.tobytes()


def _create_draft(exam_env: SimpleNamespace, title: str = "PDF Workflow Exam") -> dict:
    resp = exam_env.client.post(
        "/api/admin/exams",
        headers=exam_env.admin_headers,
        json={"title": title, "duration_minutes": 30},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_reimport_keeps_successful_crop_repairs_but_not_failed_repairs(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.exams import router as exams_router
    from app.exams.pdf_storage import has_reviewed_crop, load_regions

    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    process = exams_router._process_pdf_upload_sync

    def flagged_process(data: bytes) -> tuple:
        result = process(data)
        result[0][0].crop_valid = False
        result[0][0].warnings.append("Crop failed: partially clipped graphic; expand the crop.")
        return result

    monkeypatch.setattr(exams_router, "_process_pdf_upload_sync", flagged_process)
    exam = _create_draft(exam_env)
    pdf = _build_pdf([
        [((72, 90), "1 Which option is correct?"), ((72, 110), "A Alpha B Beta C Gamma D Delta")]
    ])

    def preview(key: str = "1 B") -> dict:
        response = exam_env.client.post(
            f"/api/admin/exams/{exam['id']}/import-pdf",
            headers=exam_env.admin_headers,
            files={"file": ("paper.pdf", pdf, "application/pdf")},
            data={"answer_key_text": key},
        )
        assert response.status_code == 200, response.text
        return response.json()

    initial = preview()
    assert len(initial["invalid_questions"]) == 1
    source = initial["source_file_id"]
    endpoint = f"/api/admin/exams/{exam['id']}/sources/{source}/questions/1/crops"
    invalid = exam_env.client.put(endpoint, headers=exam_env.admin_headers, json={
        "regions": [{"page": 1, "bbox": [0, 0, 595, 10]}], "strict": False,
    })
    assert invalid.status_code == 422
    assert len(preview()["invalid_questions"]) == 1
    repaired = exam_env.client.put(endpoint, headers=exam_env.admin_headers, json={
        "regions": [{"page": 1, "bbox": [40, 50, 550, 150]}], "strict": False,
    })
    assert repaired.status_code == 200, repaired.text
    repeated = preview()
    assert len(repeated["valid_questions"]) == 1
    assert not repeated["valid_questions"][0]["errors"]
    assert not any(w.startswith("Crop failed:") for w in repeated["valid_questions"][0]["warnings"])
    assert len(preview("")["invalid_questions"]) == 1  # Repair does not bypass answer validation.
    from uuid import UUID

    stored = load_regions(UUID(source), 1)
    assert has_reviewed_crop(UUID(source), 1, stored)
    stored[0]["bbox"][1] += 1
    assert not has_reviewed_crop(UUID(source), 1, stored)


def test_pdf_import_text_diagrams_equations_tables_and_answer_key_formats(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    exam = _create_draft(exam_env, "Multi-format PDF")
    pdf_bytes = _build_pdf(
        [
            [
                ((72, 90), "1 Solve x^2 + y^2 = r^2 for r > 0."),
                ((72, 110), "A Alpha  B Beta  C Gamma  D Delta"),
                ((72, 260), "2 Which diagram shows the equilibrium state?"),
                ((72, 280), "A Option A  B Option B  C Option C  D Option D"),
            ]
        ],
        draw_diagram=True,
        draw_table=True,
    )

    for key_text in (
        "1. B\n2. C",
        "1) B\n2) C",
        "1-B\n2-C",
        "1: B\n2: C",
        "Q1 B\nQ2 C",
        "1\tB\n2\tC",
        "B\nC",
        "B, C",
    ):
        resp = exam_env.client.post(
            f"/api/admin/exams/{exam['id']}/import-pdf",
            headers=exam_env.admin_headers,
            files={"file": ("exam.pdf", pdf_bytes, "application/pdf")},
            data={"answer_key_text": key_text},
        )
        assert resp.status_code == 200, (key_text, resp.text)
        body = resp.json()
        assert body["source_file_id"] is not None
        assert body["page_count"] == 1
        assert len(body["page_dimensions"]) == 1
        assert body["total_blocks"] == 2
        assert [q["answer_label"] for q in body["valid_questions"]] == ["B", "C"]


def test_pdf_import_without_answer_key_or_with_partial_or_extra_keys_retains_images(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    exam = _create_draft(exam_env, "Decoupled Key Exam")
    pdf_bytes = _build_pdf(
        [
            [
                ((72, 90), "1 First question stem here?"),
                ((72, 110), "A Alpha  B Beta  C Gamma  D Delta"),
                ((72, 250), "2 Second question stem here?"),
                ((72, 270), "A Five  B Six  C Seven  D Eight"),
            ]
        ]
    )
    for key_text, expected_answers in (
        ("", [None, None]),
        ("1. A", ["A", None]),
        ("1. A\n2. B\n3. C", ["A", "B"]),
    ):
        resp = exam_env.client.post(
            f"/api/admin/exams/{exam['id']}/import-pdf",
            headers=exam_env.admin_headers,
            files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
            data={"answer_key_text": key_text},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        all_qs = body["valid_questions"] + body["invalid_questions"]
        assert len(all_qs) == 2
        assert all(len(q["image_urls"]) >= 1 for q in all_qs)
        by_pos = {q["position"]: q["answer_label"] for q in all_qs}
        assert [by_pos[1], by_pos[2]] == expected_answers


def test_unusual_numbering_and_blank_scan_return_rendered_pages_for_manual_crop(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    exam = _create_draft(exam_env, "Manual Crop Exam")
    unusual_pdf = _build_pdf(
        [[((72, 90), "Item Alpha: What is the mass?"), ((72, 110), "A 1kg  B 2kg  C 3kg  D 4kg")]]
    )
    resp = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("unusual.pdf", unusual_pdf, "application/pdf")},
        data={"answer_key_text": ""},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    source_id = body["source_file_id"]
    assert source_id is not None
    assert body["page_count"] == 1

    # Full page render succeeds with no-store private cache headers and blocks students.
    page_resp = exam_env.client.get(
        f"/api/admin/exams/{exam['id']}/sources/{source_id}/pages/1?dpi=150",
        headers=exam_env.admin_headers,
    )
    assert page_resp.status_code == 200
    assert page_resp.headers["content-type"] == "image/png"
    assert "no-store" in page_resp.headers["cache-control"]
    assert page_resp.content.startswith(b"\x89PNG\r\n\x1a\n")

    student_page = exam_env.client.get(
        f"/api/admin/exams/{exam['id']}/sources/{source_id}/pages/1",
        headers=exam_env.student_headers,
    )
    assert student_page.status_code == 403

    # Manual normalized crop (including multi-page/multi-region) succeeds with strict=False.
    crop_resp = exam_env.client.put(
        f"/api/admin/exams/{exam['id']}/sources/{source_id}/questions/1/crops",
        headers=exam_env.admin_headers,
        json={
            "regions": [{"page": 1, "bbox_normalized": [0.05, 0.05, 0.9, 0.35]}],
            "dpi": 200,
            "strict": False,
        },
    )
    assert crop_resp.status_code == 200, crop_resp.text
    crop_data = crop_resp.json()
    assert len(crop_data["image_urls"]) == 1
    assert crop_data["regions"][0]["bbox_normalized"] is not None


def test_spanning_two_pages_and_draft_cleanup_removes_storage_files(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    exam = _create_draft(exam_env, "Cleanup Exam")
    two_page_pdf = _build_pdf(
        [
            [((72, 90), "1. Read the passage below."), ((72, 110), "Continued on next page.")],
            [((72, 90), "A Yes  B No  C Maybe  D Unknown")],
        ]
    )
    resp = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("two_page.pdf", two_page_pdf, "application/pdf")},
        data={"answer_key_text": "1. A"},
    )
    assert resp.status_code == 200, resp.text
    source_id = resp.json()["source_file_id"]
    assert source_id is not None

    crop_resp = exam_env.client.put(
        f"/api/admin/exams/{exam['id']}/sources/{source_id}/questions/1/crops",
        headers=exam_env.admin_headers,
        json={
            "regions": [
                {"page": 1, "bbox_normalized": [0.05, 0.05, 0.9, 0.3]},
                {"page": 2, "bbox_normalized": [0.05, 0.05, 0.9, 0.3]},
            ],
            "dpi": 200,
            "strict": False,
        },
    )
    assert crop_resp.status_code == 200, crop_resp.text
    assert len(crop_resp.json()["image_urls"]) == 2
    assert (tmp_path / source_id).is_dir()

    del_resp = exam_env.client.delete(
        f"/api/admin/exams/{exam['id']}",
        headers=exam_env.admin_headers,
    )
    assert del_resp.status_code == 204
    assert not (tmp_path / source_id).exists()
    assert not source_dir(source_id).exists()


def test_malformed_encrypted_and_oversized_pdfs_are_rejected(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    exam = _create_draft(exam_env, "Security Guards Exam")

    malformed = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("bad.pdf", b"%PDF-1.4\ncorrupt-payload", "application/pdf")},
    )
    assert malformed.status_code == 400

    encrypted_bytes = _build_pdf([[((72, 90), "1. Secret?")]], encrypt=True)
    encrypted = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("enc.pdf", encrypted_bytes, "application/pdf")},
    )
    assert encrypted.status_code == 400
    assert "Encrypted" in encrypted.json()["detail"]

    oversized_page_bytes = _build_pdf(
        [[((72, 90), "1. Huge page")]], width=6000.0, height=6000.0
    )
    oversized = exam_env.client.post(
        f"/api/admin/exams/{exam['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("huge.pdf", oversized_page_bytes, "application/pdf")},
    )
    assert oversized.status_code == 400
    assert "dimensions" in oversized.json()["detail"].lower()


def test_text_exam_backward_compatibility_and_alembic_0007_upgrade_downgrade(
    exam_env: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Existing text-only exam continues to work.
    exam = _create_draft(exam_env, "Text Compatibility Exam")
    save_resp = exam_env.client.put(
        f"/api/admin/exams/{exam['id']}/questions",
        headers=exam_env.admin_headers,
        json={
            "questions": [
                {
                    "question_text": "What is 2 + 2?",
                    "points": "1.00",
                    "options": [
                        {"label": "A", "option_text": "3", "is_correct": False},
                        {"label": "B", "option_text": "4", "is_correct": True},
                        {"label": "C", "option_text": "5", "is_correct": False},
                        {"label": "D", "option_text": "6", "is_correct": False},
                    ],
                }
            ]
        },
    )
    assert save_resp.status_code == 200, save_resp.text
    assert save_resp.json()["questions"][0]["image_urls"] == []

    # PostgreSQL offline DDL compilation test for 0007_pdf_import_workflow.
    backend_dir = Path(__file__).resolve().parent.parent
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
    monkeypatch.setenv("DIRECT_DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        capsys.readouterr()
        cfg = Config(str(backend_dir / "alembic.ini"))
        command.upgrade(cfg, "head", sql=True)
        ddl = capsys.readouterr().out
        assert "page_dimensions" in ddl
        assert "region_status" in ddl
        assert "extracted_text" in ddl
        assert "ck_questions_region_status" in ddl
        assert "ON DELETE SET NULL" in ddl
    finally:
        get_settings.cache_clear()


def test_phase7_security_and_failure_paths(
    exam_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shutil
    from concurrent.futures import ThreadPoolExecutor

    from app.config import get_settings
    from app.exams import router as exams_router
    from app.exams.pdf_storage import render_source_page

    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    exam_a = _create_draft(exam_env, "Exam A")
    exam_b = _create_draft(exam_env, "Exam B")
    valid_pdf = _build_pdf(
        [[((72, 90), "1 Which option is right?"), ((72, 110), "A Alpha  B Beta  C Gamma  D Delta")]]
    )

    # 1. Forged MIME type
    forged = exam_env.client.post(
        f"/api/admin/exams/{exam_a['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("evil.html", valid_pdf, "text/html")},
    )
    assert forged.status_code == 400
    assert str(tmp_path) not in forged.text

    # 2. Invalid PDF signature
    bad_sig = exam_env.client.post(
        f"/api/admin/exams/{exam_a['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("fake.pdf", b"NOT_A_PDF_HEADER", "application/pdf")},
    )
    assert bad_sig.status_code == 400
    assert str(tmp_path) not in bad_sig.text

    # 3. Oversized PDF bytes, excessive page count, excessive pixel count
    monkeypatch.setenv("MAX_PDF_BYTES", "50")
    get_settings.cache_clear()
    try:
        too_big = exam_env.client.post(
            f"/api/admin/exams/{exam_a['id']}/import-pdf",
            headers=exam_env.admin_headers,
            files={"file": ("big.pdf", valid_pdf, "application/pdf")},
        )
        assert too_big.status_code == 400
    finally:
        monkeypatch.delenv("MAX_PDF_BYTES", raising=False)
        get_settings.cache_clear()

    monkeypatch.setenv("MAX_PDF_PAGES", "1")
    get_settings.cache_clear()
    try:
        two_pages = _build_pdf([[((72, 90), "1 Q1")], [((72, 90), "2 Q2")]])
        too_many_pages = exam_env.client.post(
            f"/api/admin/exams/{exam_a['id']}/import-pdf",
            headers=exam_env.admin_headers,
            files={"file": ("pages.pdf", two_pages, "application/pdf")},
        )
        assert too_many_pages.status_code == 400
    finally:
        monkeypatch.delenv("MAX_PDF_PAGES", raising=False)
        get_settings.cache_clear()

    monkeypatch.setenv("MAX_PDF_IMAGE_PIXELS", "10")
    get_settings.cache_clear()
    try:
        doc = fitz.open(stream=valid_pdf, filetype="pdf")
        png_bytes = doc[0].get_pixmap(dpi=72, alpha=False).tobytes("png")
        doc.close()
        too_many_pixels = exam_env.client.post(
            f"/api/admin/exams/{exam_a['id']}/import-pdf",
            headers=exam_env.admin_headers,
            files={"file": ("scan.png", png_bytes, "image/png")},
        )
        assert too_many_pixels.status_code == 400
        assert "pixel" in too_many_pixels.json()["detail"].lower()
    finally:
        monkeypatch.delenv("MAX_PDF_IMAGE_PIXELS", raising=False)
        get_settings.cache_clear()

    # 4. Rendering timeout
    orig_sync = exams_router._process_pdf_upload_sync

    def _slow_sync(_data: bytes):
        import time

        time.sleep(0.2)
        return orig_sync(_data)

    monkeypatch.setattr(exams_router, "_process_pdf_upload_sync", _slow_sync)
    monkeypatch.setattr(exams_router, "get_settings", lambda: SimpleNamespace(
        MAX_PDF_BYTES=100 * 1024 * 1024,
        PDF_PROCESS_TIMEOUT_SECONDS=0.01,
    ))
    timed_out = exam_env.client.post(
        f"/api/admin/exams/{exam_a['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("slow.pdf", valid_pdf, "application/pdf")},
    )
    assert timed_out.status_code == 504
    monkeypatch.setattr(exams_router, "_process_pdf_upload_sync", orig_sync)
    monkeypatch.setattr(exams_router, "get_settings", get_settings)

    # 5. Cross-exam access, unauthorized access, retry interrupted import, and concurrency
    ok_import = exam_env.client.post(
        f"/api/admin/exams/{exam_a['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("ok.pdf", valid_pdf, "application/pdf")},
        data={"answer_key_text": "1. B"},
    )
    assert ok_import.status_code == 200
    source_id = ok_import.json()["source_file_id"]

    # Cross-exam page & crop access must return 404
    assert (
        exam_env.client.get(
            f"/api/admin/exams/{exam_b['id']}/sources/{source_id}/pages/1",
            headers=exam_env.admin_headers,
        ).status_code
        == 404
    )
    assert (
        exam_env.client.get(
            f"/api/admin/exams/{exam_b['id']}/source-images/{source_id}/1/0",
            headers=exam_env.admin_headers,
        ).status_code
        == 404
    )
    # Unauthenticated and student access to admin crop image
    assert (
        exam_env.client.get(
            f"/api/admin/exams/{exam_a['id']}/source-images/{source_id}/1/0"
        ).status_code
        == 401
    )
    assert (
        exam_env.client.get(
            f"/api/admin/exams/{exam_a['id']}/source-images/{source_id}/1/0",
            headers=exam_env.student_headers,
        ).status_code
        == 403
    )

    # Simulate interrupted storage directory and retry import
    shutil.rmtree(tmp_path / source_id)
    retry = exam_env.client.post(
        f"/api/admin/exams/{exam_a['id']}/import-pdf",
        headers=exam_env.admin_headers,
        files={"file": ("ok.pdf", valid_pdf, "application/pdf")},
        data={"answer_key_text": "1. B"},
    )
    assert retry.status_code == 200
    assert (tmp_path / source_id / "source.pdf").is_file()

    # Concurrent requests for the same page image
    from uuid import UUID

    sid_uuid = UUID(source_id)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: render_source_page(sid_uuid, 1, dpi=150), range(4)))
    assert all(r == results[0] and r.startswith(b"\x89PNG\r\n\x1a\n") for r in results)
    assert not list((tmp_path / source_id).glob("*.tmp"))
