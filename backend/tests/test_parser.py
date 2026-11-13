"""Comprehensive unit & invariant tests for the deterministic bulk MCQ parser."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.exams.parser import parse_questions, parse_questions_with_answer_key
from app.exams.schemas import (
    OptionLabel,
    ParsedOption,
    ParsedQuestion,
    ParseQuestionsError,
    ParseQuestionsRequest,
    ParseQuestionsResponse,
)
from app.exams.service import parse_questions_service


def _assert_response_invariants(response: ParseQuestionsResponse) -> None:
    """Verify global and per-question ParseQuestionsResponse invariants."""
    assert response.total_blocks == len(response.valid_questions) + len(response.invalid_questions)
    assert response.valid_count == len(response.valid_questions)
    assert response.error_count == len(response.errors)

    for q in response.valid_questions:
        assert q.valid is True
        assert q.errors == []
        assert q.answer_label in ("A", "B", "C", "D")
        assert 2 <= len(q.options) <= 4
        assert [o.label for o in q.options] == ["A", "B", "C", "D"][: len(q.options)]
        assert any(o.label == q.answer_label for o in q.options)

    for q in response.invalid_questions:
        assert q.valid is False
        assert len(q.errors) >= 1
        block_msgs = [e.message for e in response.errors if e.block_index == q.position]
        assert q.errors == block_msgs


# ---------------------------------------------------------------------------
# Happy paths & supported format variants
# ---------------------------------------------------------------------------


def test_parse_canonical_four_option_mcq() -> None:
    raw = """
    1. What is the capital of Ghana?
    A. Accra
    B. Kumasi
    C. Tamale
    D. Takoradi
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 1
    assert resp.valid_count == 1
    assert resp.error_count == 0

    q = resp.valid_questions[0]
    assert isinstance(q, ParsedQuestion)
    assert isinstance(q.options[0], ParsedOption)
    assert q.position == 1
    assert q.points == Decimal("1.00")
    assert q.question_text == "What is the capital of Ghana?"
    assert [(o.label, o.option_text) for o in q.options] == [
        ("A", "Accra"),
        ("B", "Kumasi"),
        ("C", "Tamale"),
        ("D", "Takoradi"),
    ]
    assert q.answer_label == "A"


def test_separate_answer_key_marks_exact_numbered_questions() -> None:
    questions = """1. First?
A. Yes
B. No
2. Second?
A. Left
B. Right"""
    response = parse_questions_with_answer_key(questions, "1. B\n2: A")
    _assert_response_invariants(response)
    assert response.valid_count == 2
    assert [q.answer_label for q in response.valid_questions] == ["B", "A"]


@pytest.mark.parametrize(
    "key",
    ["1. B", "1. B\n1. A\n2. A", "1. B\n2. C", "1. B\n2. A\n3. B", "1. B\n2. Z"],
)
def test_separate_answer_key_rejects_incomplete_ambiguous_or_invalid_key(key: str) -> None:
    questions = """1. First?
A. Yes
B. No
2. Second?
A. Left
B. Right"""
    response = parse_questions_with_answer_key(questions, key)
    _assert_response_invariants(response)
    assert response.valid_count == 0
    assert all(q.answer_label is None for q in response.invalid_questions)


def test_separate_answer_key_rejects_inline_conflict() -> None:
    questions = "1. First?\nA. Yes\nB. No\nANSWER: A"
    response = parse_questions_with_answer_key(questions, "1. B")
    _assert_response_invariants(response)
    assert response.valid_count == 0
    assert any("inline answer" in error.message for error in response.errors)


def test_parse_two_and_three_option_questions() -> None:
    raw = """
    1. Water boils at 100 degrees Celsius at standard atmospheric pressure.
    A. True
    B. False
    ANSWER: A

    2. Which state of matter has a definite volume but no fixed shape?
    A. Solid
    B. Liquid
    C. Gas
    ANSWER: B
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 2
    assert resp.valid_count == 2
    assert resp.error_count == 0
    assert [len(q.options) for q in resp.valid_questions] == [2, 3]
    assert [q.answer_label for q in resp.valid_questions] == ["A", "B"]


def test_parse_mixed_header_option_and_answer_variants() -> None:
    raw = """
    1.   First   question?
    a. Choice one
    b) Choice two
    Answer: b.

    Q2: Second question?
    A) Alpha
    B) Beta
    C) Gamma
    Ans: C

    3) Third question?
    A. One
    B. Two
    C. Three
    D. Four
    Correct Answer: d)

    q4. Fourth question?
    a) Yes
    b. No
    ANSWER:   a
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 4
    assert resp.valid_count == 4
    assert resp.error_count == 0
    assert [q.question_text for q in resp.valid_questions] == [
        "First question?",
        "Second question?",
        "Third question?",
        "Fourth question?",
    ]
    assert [q.answer_label for q in resp.valid_questions] == ["B", "C", "D", "A"]


def test_parse_multiline_stem_and_multiline_options() -> None:
    raw = """
    1.
    Consider a cylinder of radius 2 cm.
    What is the approximate value of
    pi used to compute its circumference?
    A. Roughly 3.14
       rounded to two decimal places
    B. Exactly 4.00
       as an integer constant
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 1
    assert resp.error_count == 0
    q = resp.valid_questions[0]
    assert q.question_text == (
        "Consider a cylinder of radius 2 cm. What is the approximate value of "
        "pi used to compute its circumference?"
    )
    assert q.options[0].option_text == "Roughly 3.14 rounded to two decimal places"
    assert q.options[1].option_text == "Exactly 4.00 as an integer constant"


def test_decimals_abbreviations_and_mid_sentence_numbers_do_not_split() -> None:
    raw = """
    1. Suppose a sample is collected at 8:00
    a.m. and measured against
    3.14 standards, e.g. those described by
    C.S. Lewis or observed in
    E. coli cultures back
    In 2024. Which conclusion holds?
    A. Valid measurement
    B. Invalid measurement
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 1
    assert resp.valid_count == 1
    assert resp.error_count == 0
    q = resp.valid_questions[0]
    assert "3.14 standards" in q.question_text
    assert "a.m." in q.question_text
    assert "C.S. Lewis" in q.question_text
    assert "e.g." in q.question_text
    assert "E. coli" in q.question_text
    assert "In 2024." in q.question_text


def test_crlf_cr_lf_and_utf8_bom_equivalence() -> None:
    lf = (
        "1. Capital of Ghana?\n"
        "A. Accra\n"
        "B. Kumasi\n"
        "ANSWER: A\n\n"
        "2. 2 + 2 = ?\n"
        "A. 3\n"
        "B. 4\n"
        "ANSWER: B\n"
    )
    crlf = lf.replace("\n", "\r\n")
    cr = lf.replace("\n", "\r")
    bom_crlf = "\ufeff" + crlf

    base = parse_questions(lf)
    assert parse_questions(crlf) == base
    assert parse_questions(cr) == base
    assert parse_questions(bom_crlf) == base
    assert base.valid_count == 2
    assert base.error_count == 0


# ---------------------------------------------------------------------------
# Blank, missing-header, and leading/trailing orphan failure modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["", "   \n\t\r\n  ", "\ufeff   \r\n"])
def test_empty_and_whitespace_inputs_report_zero_blocks_and_one_error(raw: str) -> None:
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 0
    assert resp.valid_count == 0
    assert resp.error_count == 1
    assert resp.errors[0].block_index == 0
    assert "empty input" in resp.errors[0].message


def test_prose_without_question_headers_reports_no_blocks_error() -> None:
    raw = """
    What is the capital of Ghana?
    A. Accra
    B. Kumasi
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 0
    assert resp.valid_count == 0
    assert resp.error_count == 1
    assert resp.errors[0].block_index == 0
    assert "no question blocks found" in resp.errors[0].message


def test_leading_orphan_text_before_question_one_is_not_silently_dropped() -> None:
    raw = """
    Stray unnumbered question?
    A. Accra
    B. Kumasi
    ANSWER: A

    1. Valid question?
    A. Yes
    B. No
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 1
    assert resp.valid_count == 1
    assert resp.error_count == 1
    assert resp.errors[0].block_index == 0
    assert "before first question header" in resp.errors[0].message


def test_trailing_orphan_text_after_answer_errors_instead_of_corrupting_stem() -> None:
    raw = """
    1. Capital of Ghana?
    A. Accra
    B. Kumasi
    ANSWER: A
    Some trailing orphan text that must not enter question_text
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 1
    assert resp.valid_count == 0
    assert resp.error_count == 1
    q = resp.invalid_questions[0]
    assert q.question_text == "Capital of Ghana?"
    assert "trailing content after ANSWER" in q.errors[0]


def test_options_after_answer_are_rejected() -> None:
    raw = """
    1. Capital of Ghana?
    ANSWER: A
    A. Accra
    B. Kumasi
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    q = resp.invalid_questions[0]
    assert q.answer_label is None
    assert any("unexpected option line after ANSWER" in msg for msg in q.errors)


# ---------------------------------------------------------------------------
# Question stem & option validation failure modes
# ---------------------------------------------------------------------------


def test_empty_question_text_is_rejected() -> None:
    raw = """
    1.
    A. Yes
    B. No
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    assert resp.error_count == 1
    assert resp.invalid_questions[0].question_text == ""
    assert resp.invalid_questions[0].errors == ["empty question text"]


def test_zero_and_single_option_questions_are_rejected() -> None:
    raw = """
    1. No options here?
    ANSWER: A

    2. Only one option here?
    A. Sole choice
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 2
    assert resp.valid_count == 0
    assert any("no options provided" in msg for msg in resp.invalid_questions[0].errors)
    assert any("at least 2 options are required" in msg for msg in resp.invalid_questions[1].errors)


def test_unsupported_fifth_option_e_triggers_clear_error() -> None:
    raw = """
    1. Closest planet to the Sun?
    A. Mercury
    B. Venus
    C. Earth
    D. Mars
    E. Jupiter
       wrapped line for E
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    q = resp.invalid_questions[0]
    assert q.question_text == "Closest planet to the Sun?"
    assert q.options[-1].option_text == "Mars"
    assert any("unsupported option label 'E'" in msg for msg in q.errors)


def test_gap_labels_and_out_of_order_labels_are_rejected() -> None:
    raw = """
    1. Skipped B?
    A. First
    C. Third
    D. Fourth
    ANSWER: A

    2. Out of order?
    B. Second
    A. First
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    assert any("expected 'B', found 'C'" in msg for msg in resp.invalid_questions[0].errors)
    assert any("expected 'A', found 'B'" in msg for msg in resp.invalid_questions[1].errors)


def test_duplicate_option_labels_including_empty_first_duplicate() -> None:
    raw = """
    1. Duplicate labels?
    A.
    a) Accra
    B. Kumasi
    ANSWER: B
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    msgs = resp.invalid_questions[0].errors
    assert "option 'A' has empty text" in msgs
    assert "duplicate option label 'A'" in msgs


def test_empty_option_text_is_rejected() -> None:
    raw = "1. Missing B text?\nA. Yes\nB.   \nANSWER: A\n"
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    assert resp.invalid_questions[0].errors == ["option 'B' has empty text"]


def test_answer_referencing_empty_option_sets_answer_label_none() -> None:
    raw = "1. Empty A?\nA.\nB. Valid\nANSWER: A\n"
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    q = resp.invalid_questions[0]
    assert q.answer_label is None
    assert "option 'A' has empty text" in q.errors


def test_broken_block_terminates_cleanly_at_next_numbered_header() -> None:
    raw = """
    1. Incomplete first question?

    Question 2: Complete second question?
    A. Yes
    B. No
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 2
    assert resp.valid_count == 1
    assert [q.position for q in resp.valid_questions] == [2]
    assert [q.position for q in resp.invalid_questions] == [1]
    assert "no options provided for question" in resp.invalid_questions[0].errors
    assert "missing answer (ANSWER: X)" in resp.invalid_questions[0].errors


def test_multiple_answers_with_one_invalid_never_guesses() -> None:
    raw = """
    1. Ambiguous and invalid?
    A. One
    B. Two
    ANSWER: A
    ANSWER: E
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    q = resp.invalid_questions[0]
    assert q.answer_label is None
    assert any("multiple ANSWER lines" in msg for msg in q.errors)
    assert any("invalid answer label 'E'" in msg for msg in q.errors)


def test_duplicate_identical_option_text_is_rejected_case_insensitively() -> None:
    raw = """
    1. Capital of Ghana?
    A. Accra
    B.   accra
    C. Kumasi
    D. Tamale
    ANSWER: A
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.valid_count == 0
    assert any(
        "duplicate option text for labels 'A' and 'B'" in msg
        for msg in resp.invalid_questions[0].errors
    )


# ---------------------------------------------------------------------------
# Answer validation & strict never-infer checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer_block", "expected_fragment"),
    [
        ("", "missing answer"),
        ("ANSWER:", "missing answer label"),
        ("ANSWER: E", "invalid answer label 'E'"),
        ("ANSWER: foo", "invalid answer label 'foo'"),
        ("ANSWER: A, B", "invalid answer label 'A, B'"),
        ("ANSWER: D", "references an option that does not exist"),
        ("ANSWER: A\nANSWER: B", "multiple ANSWER lines"),
        ("ANSWER: B\nANSWER: B", "multiple ANSWER lines"),
    ],
)
def test_bad_missing_duplicate_or_dangling_answers_never_default_to_a(
    answer_block: str,
    expected_fragment: str,
) -> None:
    raw = f"1. Pick one?\nA. First\nB. Second\nC. Third\n{answer_block}"
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 1
    assert resp.valid_count == 0
    assert resp.error_count >= 1

    q = resp.invalid_questions[0]
    assert q.question_text == "Pick one?"
    assert q.answer_label is None
    assert any(expected_fragment in msg for msg in q.errors)


# ---------------------------------------------------------------------------
# Mixed batches, tallies, schemas, and service wrapper
# ---------------------------------------------------------------------------


def test_mixed_valid_and_invalid_batch_tallies_and_positions() -> None:
    raw = """
    1. Valid first?
    A. One
    B. Two
    ANSWER: B

    2. Broken second?
    A. Alpha
    B. Beta
    ANSWER: E

    3. Valid third?
    A. Red
    B. Blue
    C. Green
    ANSWER: C
    """
    resp = parse_questions(raw)
    _assert_response_invariants(resp)
    assert resp.total_blocks == 3
    assert resp.valid_count == 2
    assert resp.error_count == 1
    assert [q.position for q in resp.valid_questions] == [1, 3]
    assert [q.position for q in resp.invalid_questions] == [2]
    assert resp.invalid_questions[0].answer_label is None
    assert resp.errors == [
        ParseQuestionsError(
            block_index=2,
            message="invalid answer label 'E' (expected one of A, B, C, D)",
        )
    ]


def test_schema_types_and_service_wrapper_compatibility() -> None:
    req = ParseQuestionsRequest(raw_text="1. Valid?\nA. Yes\nB. No\nANSWER: A")
    resp = parse_questions_service(req.raw_text)
    _assert_response_invariants(resp)
    label: OptionLabel | None = resp.valid_questions[0].answer_label
    assert label == "A"
