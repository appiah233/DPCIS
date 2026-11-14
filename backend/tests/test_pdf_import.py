"""Acceptance coverage for the supplied atomic structure paper."""

from __future__ import annotations

import json
import random
import re
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import fitz
import pytest

from app.attempts.grading import compute_mcq_grade
from app.exams.parser import parse_questions_with_answer_key
from app.exams.pdf_import import (
    OCRUnavailable,
    detect_pdf_questions,
    detect_questions_with_ocr,
    render_region,
    validate_pdf,
)
from app.exams.pdf_storage import load_image, regenerate_crops, store_pdf

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED = "BCACCADBBCCCCAADBAACCBCC"
REFERENCE = FIXTURES / "pdfs" / "cie_igcse_chem_2_2_atomic_structure_qp.expected.json"


def test_sample_detects_all_questions_and_preserves_diagrams() -> None:
    doc = validate_pdf((FIXTURES / "atomic_structure_qp.pdf").read_bytes())
    try:
        questions = detect_pdf_questions(doc)
        assert [q.number for q in questions] == list(range(1, 25))
        assert questions[17].regions[0].page == 6
        assert questions[18].regions[0].page == 7
        for number in (4, 6, 15, 21):
            region = questions[number - 1].regions[0]
            assert region.bbox[3] - region.bbox[1] > 100
            png = render_region(doc, region)
            assert len(png) > 10_000
            pixmap = doc[region.page - 1].get_pixmap(
                clip=fitz.Rect(region.bbox), dpi=100, alpha=False
            )
            lower_half = pixmap.samples[(pixmap.height // 2) * pixmap.width * pixmap.n :]
            assert sum(value < 220 for value in lower_half[:: pixmap.n]) > 1_000
        for question in questions:
            for region in question.regions:
                text = doc[region.page - 1].get_text(clip=region.bbox)
                assert "PhysicsAndMathsTutor.com" not in text
                assert "PMT" not in text
    finally:
        doc.close()


def test_reference_manifest_matches_each_question() -> None:
    expected = json.loads(REFERENCE.read_text(encoding="utf-8"))
    doc = validate_pdf((FIXTURES / "atomic_structure_qp.pdf").read_bytes())
    try:
        questions = detect_pdf_questions(doc)
        assert len(doc) == expected["page_count"]
        assert len(questions) == len(expected["questions"])
        for question in questions:
            item = expected["questions"][str(question.number)]
            assert question.regions[0].page == item["page"]
            assert question.options_kind == item["options_kind"]
            section = next(
                name for name, (first, last) in expected["sections"].items()
                if first <= question.number <= last
            )
            assert question.section == section
            words = re.sub(r"\s+", " ", question.extracted_text).split()
            if words[0] == str(question.number):
                words.pop(0)
            assert " ".join(words[:len(item["first_words"].split())]) == item["first_words"]
        for first, second in expected["identical_pairs"]:
            assert first != second
            assert questions[first - 1].number == first
            assert questions[second - 1].number == second
            assert questions[first - 1].extracted_text != ""
            assert questions[second - 1].extracted_text != ""
    finally:
        doc.close()


def test_margin_shift_and_shuffled_pdf_stream_keep_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    source = validate_pdf((FIXTURES / "atomic_structure_qp.pdf").read_bytes())
    shifted = fitz.open()
    try:
        page = shifted.new_page(width=source[0].rect.width, height=source[0].rect.height)
        page.show_pdf_page(
            fitz.Rect(25, 0, source[0].rect.width + 25, source[0].rect.height),
            source, 0,
        )
        assert [q.number for q in detect_pdf_questions(shifted)] == [1, 2, 3]
        baseline = detect_pdf_questions(source)
        original = fitz.Page.get_text

        def shuffled(self: fitz.Page, option: str = "text", *args: object, **kwargs: object):
            value = original(self, option, *args, **kwargs)
            if option == "words":
                value = list(value)
                random.Random(641).shuffle(value)  # noqa: S311 - deterministic test fixture
            return value

        monkeypatch.setattr(fitz.Page, "get_text", shuffled)
        changed = detect_pdf_questions(source)
        assert [(q.number, q.extracted_text, q.options_kind, q.section) for q in changed] == [
            (q.number, q.extracted_text, q.options_kind, q.section) for q in baseline
        ]
    finally:
        shifted.close()
        source.close()


def test_drawings_and_headings_do_not_become_questions_or_options() -> None:
    doc = validate_pdf((FIXTURES / "atomic_structure_qp.pdf").read_bytes())
    try:
        questions = detect_pdf_questions(doc)
        assert [q.number for q in questions] == list(range(1, 25))
        assert all(questions[number - 1].options_kind == "table" for number in (7, 16))
        assert all(questions[number - 1].options_kind == "image" for number in (4, 21))
        assert all(not questions[number - 1].options_text for number in (4, 7, 16, 21))
        assert set(questions[8].options_text) == set("ABCD")
        assert all(label not in questions[8].options_text for label in "PQRS")
        for number, heading in ((1, "Paper 1"), (19, "Paper 2")):
            question = questions[number - 1]
            region = question.regions[0]
            assert heading not in doc[region.page - 1].get_text(clip=region.bbox)
            assert question.section == heading
    finally:
        doc.close()


def test_single_page_header_overlay_is_excluded_by_position() -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_text((450, 12), "PMT PhysicsAndMathsTutor.com")
        page.insert_text((50, 110), "1 First synthetic question starts here.")
        page.insert_text((70, 160), "A Choice one")
        page.insert_text((70, 190), "B Choice two")
        questions = detect_pdf_questions(doc)
        assert [q.number for q in questions] == [1]
        assert questions[0].regions[0].bbox[1] > 20
        assert "PMT" not in page.get_text(clip=questions[0].regions[0].bbox)
        assert "PhysicsAndMathsTutor" not in page.get_text(clip=questions[0].regions[0].bbox)
    finally:
        doc.close()


def test_second_synthetic_multi_page_variant() -> None:
    doc = fitz.open()
    try:
        first = doc.new_page(width=595, height=842)
        first.insert_text((50, 785), "1 First question continues on the next page.")
        first.insert_text((70, 810), "Read the following information carefully.")
        second = doc.new_page(width=595, height=842)
        second.insert_text((70, 70), "Additional information for the first question.")
        second.insert_text((70, 110), "A First choice")
        second.insert_text((70, 140), "B Second choice")
        second.insert_text((50, 260), "2 Next question starts here.")
        second.insert_text((70, 300), "A Choice one")
        second.insert_text((70, 330), "B Choice two")
        questions = detect_pdf_questions(doc)
        assert [q.number for q in questions] == [1, 2]
        assert [region.page for region in questions[0].regions] == [1, 2]
        assert questions[1].regions[0].page == 2
    finally:
        doc.close()


def test_sample_mark_scheme_key() -> None:
    doc = validate_pdf((FIXTURES / "atomic_structure_ms.pdf").read_bytes())
    try:
        text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
    # The mark scheme text layer places each cell on its own line.
    questions = "\n".join(
        f"{number} Question?\nA. One\nB. Two\nC. Three\nD. Four" for number in range(1, 25)
    )
    response = parse_questions_with_answer_key(questions, text)
    assert response.valid_count == 24
    assert "".join(q.answer_label or "?" for q in response.valid_questions) == EXPECTED


def test_sample_first_answer_grades_b_only() -> None:
    question_id = uuid4()
    option_ids = {label: uuid4() for label in "ABCD"}
    options = [{"id": option_ids[label], "is_correct": label == "B"} for label in "ABCD"]
    for label in "ABCD":
        result = compute_mcq_grade(
            attempt_questions=[{"question_id": question_id, "points": Decimal(1)}],
            options_by_question={question_id: options},
            answers_by_question={question_id: option_ids[label]},
            pass_mark=Decimal(50),
        )
        assert result.correct_answers == (1 if label == "B" else 0)


def test_pdf_upload_rejects_non_pdf_and_encrypted_file() -> None:
    with pytest.raises(ValueError, match="not a PDF"):
        validate_pdf(b"not a PDF")
    document = fitz.open()
    document.new_page()
    encrypted = document.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="student"
    )
    document.close()
    with pytest.raises(ValueError, match="Encrypted PDFs"):
        validate_pdf(encrypted)


def test_regeneration_is_byte_identical_with_same_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uuid import uuid4

    monkeypatch.setenv("EXAM_PDF_STORAGE_DIR", str(tmp_path))
    data = (FIXTURES / "atomic_structure_qp.pdf").read_bytes()
    doc = validate_pdf(data)
    try:
        questions = detect_pdf_questions(doc)
    finally:
        doc.close()
    source_id = uuid4()
    store_pdf(source_id, data, questions)
    before = load_image(source_id, 4, 0)
    regions = regenerate_crops(source_id, 4, dpi=200, padding=0)
    assert regions[0]["page"] == 2
    assert load_image(source_id, 4, 0) == before
    with pytest.raises(ValueError, match="at least 30 pt"):
        regenerate_crops(source_id, 4, [{"page": 2, "bbox": [0, 100, 500, 110]}])
    assert load_image(source_id, 4, 0) == before


def test_two_column_fixture_detects_all_four_questions() -> None:
    doc = validate_pdf((FIXTURES / "two_column.pdf").read_bytes())
    try:
        questions = detect_pdf_questions(doc)
        assert [question.number for question in questions] == [1, 2, 3, 4]
        assert questions[0].regions[0].bbox[2] == 300
        assert questions[2].regions[0].bbox[0] == 300
    finally:
        doc.close()


def test_spanning_fixture_keeps_two_ordered_page_regions() -> None:
    doc = validate_pdf((FIXTURES / "spanning_pages.pdf").read_bytes())
    try:
        questions = detect_pdf_questions(doc)
        assert [question.number for question in questions] == [1, 2]
        assert [region.page for region in questions[0].regions] == [1, 2]
    finally:
        doc.close()


def test_image_only_fixture_reports_optional_ocr_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    doc = validate_pdf((FIXTURES / "scanned_image_only.pdf").read_bytes())
    try:
        assert detect_pdf_questions(doc) == []
        monkeypatch.setitem(sys.modules, "pytesseract", None)
        with pytest.raises(OCRUnavailable, match="OCR is needed"):
            detect_questions_with_ocr(doc)
    finally:
        doc.close()


def test_image_only_fixture_ocr_geometry_with_stubbed_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    from types import SimpleNamespace

    fake_ocr = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        TesseractNotFoundError=RuntimeError,
        image_to_data=lambda *_args, **_kwargs: {
            "text": ["1", "Question", "2", "Question"],
            "conf": [95, 95, 95, 95],
            "left": [111, 173, 111, 173],
            "top": [270, 270, 825, 825],
            "height": [35, 35, 35, 35],
        },
    )
    fake_image = SimpleNamespace(frombytes=lambda *_args: object())
    monkeypatch.setitem(sys.modules, "pytesseract", fake_ocr)
    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=fake_image))
    doc = validate_pdf((FIXTURES / "scanned_image_only.pdf").read_bytes())
    try:
        questions = detect_questions_with_ocr(doc)
        assert [question.number for question in questions] == [1, 2]
        assert all(any("OCR used" in warning for warning in q.warnings) for q in questions)
    finally:
        doc.close()
