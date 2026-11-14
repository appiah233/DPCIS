"""Deterministic bulk MCQ question-text parser (Literate Engineering spec).

Problem
-------
Convert raw admin-pasted multiple-choice question text into a structured
preview (:class:`ParseQuestionsResponse`) partitioning well-formed items
(``valid_questions``) from defective blocks (``invalid_questions``) with
actionable diagnostics (``errors``), without persisting anything to the
database and without ever guessing or inferring missing/invalid answers.

Supported Format & Variants
---------------------------
Canonical block::

    1. What is the capital of Ghana?
    A. Accra
    B. Kumasi
    C. Tamale
    D. Takoradi
    ANSWER: A

Accepted header, option, and answer variants:
* Question headers at start of line: ``1. ``, ``1) ``, ``Q1. ``, ``Q1: ``,
  ``Q1) ``, ``Question 1: `` (case-insensitive ``Q``/``Question``; also bare
  headers like ``1.`` followed by question text on the next line).
* Option prefixes at start of line: ``A.``–``D.``, ``A)``–``D)``, lowercase
  ``a.``–``d.``, ``a)``–``d)``. Dot-delimited option markers require trailing
  whitespace or end-of-line so abbreviations such as ``a.m.`` or ``C.S.``
  are never misclassified as options.
* Answer directives at start of line (case-insensitive): ``ANSWER: X``,
  ``Ans: X``, ``Correct Answer: X``, optionally with trailing ``.`` or ``)``
  (e.g., ``Answer: b.``).
* Multiline question stems (before options) and multiline option text
  (before the next option, answer directive, or question header).
* Input normalization: optional leading UTF-8 BOM (``\\ufeff``) is stripped,
  and ``\\r\\n`` / ``\\r`` line endings are normalized to ``\\n``.

Invariants
----------
1. **Line-Ending & BOM Invariance:** Identical content with LF, CRLF, CR,
   or a leading UTF-8 BOM produces identical :class:`ParseQuestionsResponse`.
2. **Never Guess / Never Infer Answers:** Missing, empty, invalid (e.g.,
   ``ANSWER: E``, ``ANSWER: foo``), duplicate, or dangling answers MUST yield
   ``answer_label=None`` and ``valid=False``. Never fall back to ``"A"``.
3. **Valid-Block Soundness:** Every entry in ``valid_questions`` has
   ``valid=True``, ``errors=[]``, non-empty ``question_text``, 2 to 4 options
   with contiguous labels starting at ``"A"`` (``A..B``, ``A..C``, or
   ``A..D``), unique labels, non-empty and distinct option texts
   (case-insensitive after whitespace normalization), and an explicit
   ``answer_label`` matching an existing option in that block.
4. **Diagnostic Consistency:** For every question block ``q``,
   ``q.valid == (len(q.errors) == 0)`` and
   ``q.errors == [e.message for e in response.errors if e.block_index == q.position]``.
   Tallies satisfy ``total_blocks == len(valid_questions) + len(invalid_questions)``,
   ``valid_count == len(valid_questions)``, and ``error_count == len(errors)``.

Assumptions & Design Decisions
------------------------------
* Option labels are restricted to ``A``–``D`` (matching database constraint
  ``ck_question_options_label_valid`` and UI circular badges ``A``–``D``).
  Unsupported labels (``E.``, ``F.``, etc.) appearing after options start
  trigger an explicit error rather than leaking into option/question text.
* Duplicate option text comparison normalizes internal whitespace and folds
  case (``.casefold()``) because students cannot reliably distinguish two
  visually identical options (especially when options are randomized).
* Non-blank lines before Question #1 (leading orphan text) are reported at
  ``block_index=0`` instead of being silently discarded.
* Non-blank lines after ``ANSWER:`` (before the next numbered header) are
  reported as trailing/malformed block errors instead of corrupting
  ``question_text`` or any option.

Edge Cases Handled
------------------
* Empty, whitespace-only, or BOM-only inputs -> ``total_blocks=0, error_count=1``.
* Prose without any numbered question header -> ``total_blocks=0, error_count=1``.
* Decimals (``3.14``), mid-sentence numbers (``In 2024.``), ratios (``1:2``),
  and abbreviations (``a.m.``, ``C.S.``, ``e.g.``, ``E. coli`` inside stem).
* Empty question text (``1.\\nA. Yes\\nB. No\\nANSWER: A``).
* Fewer than 2 options, empty option text, duplicate option labels (even when
  an earlier duplicate is empty), non-sequential/gap labels (``A, C`` or
  ``B, C``), unsupported labels (``E.``), and duplicate option texts.
* Missing ``ANSWER:``, empty ``ANSWER:``, bad answer (``ANSWER: E`` / ``foo``),
  multiple ``ANSWER:`` directives, answer referencing missing option, and
  options appearing after ``ANSWER:``.

Correctness & Complexity
------------------------
All regular expressions are line-anchored (``^...$``) with disjoint branches
and no nested quantifiers (linear-time ``O(L)`` per line, ReDoS-safe). Input
normalization, block segmentation, and state-machine parsing run in a single
pass in ``O(N)`` time and ``O(N)`` space where ``N = len(raw_text)``. Each
block contains at most 4 valid option labels, so per-block option validation
is ``O(1)``.

Test Strategy
-------------
Verified in ``backend/tests/test_parser.py`` across:
* Happy paths (2/3/4 options, mixed ``1.`` / ``1)`` / ``Q1.`` / ``Q2:`` /
  ``Q3)``, lowercase ``a.``/``a)``, multiline stems, multiline options).
* CRLF/CR/LF parity, UTF-8 BOM stripping, whitespace normalization, and
  stem preservation for ``3.14``, ``a.m.``, ``C.S.``, ``e.g.``, ``In 2024.``.
* Every failure mode: blank input, no headers, leading/trailing orphan text,
  empty stem, 0/1 options, empty option, duplicate labels, gap labels,
  unsupported ``E.``, duplicate option text, missing/empty/invalid/duplicate/
  dangling ``ANSWER:``, options after ``ANSWER:``, and mixed batches verifying
  ``total_blocks``, ``valid_count``, ``error_count``, and zero answer guessing.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import Enum
from typing import cast

from app.exams.schemas import (
    OptionLabel,
    ParsedOption,
    ParsedQuestion,
    ParseQuestionsError,
    ParseQuestionsResponse,
)

# Disjoint, line-anchored patterns (O(L) per line, ReDoS-safe):
# - Q/Question headers allow `:`, `.`, or `)` (`Q1:`, `Q1.`, `Q1)`).
# - Plain numeric headers (`1.`, `1)`) require whitespace or EOL after the
#   delimiter so decimals like `3.14` never trigger a question boundary.
QUESTION_START = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*(\d+)\s*(?::(?:\s*(.*))|[\.\)](?:\s+(.*)|$)|(?:\s+(.*)|$))|(\d+)(?:[\.\)](?:\s+(.*)|$)|\s+(.*)))",
    re.IGNORECASE,
)

# Dot-delimited options (`A. `) require whitespace or EOL after `.` so
# abbreviations like `a.m.` or `C.S.` inside stems are never misclassified.
OPTION_LINE = re.compile(r"^\s*([A-Da-d])(?:\.(?:\s+(.*)|$)|\)(?:\s*(.*)))$")
UNSUPPORTED_OPTION_LINE = re.compile(
    r"^\s*([E-Ze-z])(?:\.(?:\s+(.*)|$)|\)(?:\s*(.*)))$"
)

# Match ANY `ANSWER:` / `ANS:` / `CORRECT ANSWER:` directive regardless of value
# so invalid values like `ANSWER: E` or empty `ANSWER:` are caught cleanly.
ANSWER_DIRECTIVE = re.compile(
    r"^\s*(?:CORRECT\s+ANSWER|ANSWER|ANS)\s*:\s*(.*)$",
    re.IGNORECASE,
)
ANSWER_VALUE = re.compile(r"^([A-Za-z])[\.\)]?$")
ANSWER_KEY_ENTRY = re.compile(
    r"(?<!\w)(?:Q(?:uestion)?\s*)?(\d+)\s*[.):-]?\s*([A-Za-z])\b",
    re.IGNORECASE,
)
ANSWER_KEY_ROW = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*)?(\d+)\s*[.):-]?\s*([A-Za-z])(?:\s+(\d+))?\s*$",
    re.IGNORECASE,
)

VALID_LABELS: tuple[OptionLabel, ...] = ("A", "B", "C", "D")
DEFAULT_POINTS = Decimal("1.00")


class _BlockState(Enum):
    STEM = "stem"
    OPTIONS = "options"
    ANSWERED = "answered"


def _normalize_input(raw_text: str) -> str:
    """Strip optional UTF-8 BOM and normalize CRLF/CR line endings to LF."""
    return raw_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def _normalize_whitespace(text: str) -> str:
    """Collapse internal runs of whitespace and trim ends."""
    return " ".join(text.split())


def _extract_question_remainder(match: re.Match[str]) -> str:
    """Extract normalized stem text from the first matched tail group."""
    for group_idx in (2, 3, 4, 6, 7):
        val = match.group(group_idx)
        if val is not None:
            return _normalize_whitespace(val)
    return ""


def _extract_option_remainder(match: re.Match[str]) -> str:
    """Extract normalized option text from `.` or `)` capture groups."""
    raw = match.group(2) if match.group(2) is not None else (match.group(3) or "")
    return _normalize_whitespace(raw)


def _segment_blocks(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Split normalized lines into leading orphan lines and numbered blocks."""
    leading_orphan_lines: list[str] = []
    blocks: list[list[str]] = []
    current: list[str] | None = None

    for line in lines:
        match = QUESTION_START.match(line)
        expected = len(blocks) + (2 if current is not None else 1)
        if match and int(match.group(1) or match.group(5)) == expected:
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
        elif line.strip():
            leading_orphan_lines.append(line)

    if current is not None:
        blocks.append(current)

    return leading_orphan_lines, blocks


def _parse_answer_value(raw_value: str) -> tuple[OptionLabel | None, str | None]:
    """Validate raw text following an ANSWER directive without guessing."""
    cleaned = _normalize_whitespace(raw_value)
    if not cleaned:
        return None, "missing answer label after 'ANSWER:'"

    match = ANSWER_VALUE.match(cleaned)
    if not match:
        return None, f"invalid answer label '{cleaned}' (expected one of A, B, C, D)"

    candidate = match.group(1).upper()
    if candidate not in VALID_LABELS:
        return None, f"invalid answer label '{candidate}' (expected one of A, B, C, D)"

    return cast(OptionLabel, candidate), None


def _validate_options(
    option_entries: list[tuple[OptionLabel, list[str]]],
    unsupported_labels: list[str],
) -> tuple[list[ParsedOption], dict[OptionLabel, str], list[OptionLabel], list[str]]:
    """Validate option occurrences for count, emptiness, duplicates, and order."""
    errors: list[str] = []
    for bad_label in unsupported_labels:
        errors.append(
            f"unsupported option label '{bad_label}' (only A, B, C, D are supported)"
        )

    distinct_order: list[OptionLabel] = []
    label_counts: dict[OptionLabel, int] = {}
    first_valid_text: dict[OptionLabel, str] = {}
    empty_reported: set[OptionLabel] = set()

    for label, parts in option_entries:
        label_counts[label] = label_counts.get(label, 0) + 1
        if label not in distinct_order:
            distinct_order.append(label)

        text = _normalize_whitespace(" ".join(parts))
        if not text:
            if label not in empty_reported:
                errors.append(f"option '{label}' has empty text")
                empty_reported.add(label)
        elif label not in first_valid_text:
            first_valid_text[label] = text

    for label in distinct_order:
        if label_counts[label] > 1:
            errors.append(f"duplicate option label '{label}'")

    if len(distinct_order) == 0:
        errors.append("no options provided for question")
    elif len(distinct_order) < 2:
        errors.append(f"at least 2 options are required (found {len(distinct_order)})")
    else:
        expected_seq = list(VALID_LABELS[: len(distinct_order)])
        if distinct_order != expected_seq:
            for actual, expected in zip(distinct_order, expected_seq, strict=True):
                if actual != expected:
                    errors.append(
                        "options must be sequential starting from 'A' without gaps "
                        f"(expected '{expected}', found '{actual}')"
                    )
                    break

    seen_texts: dict[str, OptionLabel] = {}
    for label in distinct_order:
        text = first_valid_text.get(label)
        if text is None:
            continue
        folded = text.casefold()
        if folded in seen_texts:
            errors.append(
                f"duplicate option text for labels '{seen_texts[folded]}' and '{label}'"
            )
        else:
            seen_texts[folded] = label

    preview_options = [
        ParsedOption(label=label, option_text=first_valid_text[label])
        for label in VALID_LABELS
        if label in first_valid_text
    ]
    return preview_options, first_valid_text, distinct_order, errors


def _parse_and_validate_block(
    block_lines: list[str],
    block_index: int,
) -> tuple[ParsedQuestion, list[ParseQuestionsError]]:
    """Parse and validate one numbered question block using an explicit state machine."""
    header_match = QUESTION_START.match(block_lines[0])
    question_parts: list[str] = []
    if header_match is not None:
        head_text = _extract_question_remainder(header_match)
        if head_text:
            question_parts.append(head_text)

    state = _BlockState.STEM
    option_entries: list[tuple[OptionLabel, list[str]]] = []
    unsupported_labels: list[str] = []
    unsupported_seen: set[str] = set()
    answer_label: OptionLabel | None = None
    answer_count = 0
    answer_errors: list[str] = []
    structural_errors: list[str] = []
    trailing_reported = False
    option_after_answer_reported = False
    multiple_answers_reported = False
    in_unsupported_option = False

    for line in block_lines[1:]:
        if not line.strip():
            continue

        am = ANSWER_DIRECTIVE.match(line)
        if am:
            in_unsupported_option = False
            answer_count += 1
            parsed_ans, ans_err = _parse_answer_value(am.group(1))
            if answer_count == 1:
                answer_label = parsed_ans
            else:
                # Multiple ANSWER directives are ambiguous; never guess between them.
                answer_label = None
                if not multiple_answers_reported:
                    answer_errors.append("multiple ANSWER lines found in question block")
                    multiple_answers_reported = True
            if ans_err is not None:
                answer_errors.append(ans_err)
            state = _BlockState.ANSWERED
            continue

        om = OPTION_LINE.match(line)
        if om:
            in_unsupported_option = False
            if state == _BlockState.ANSWERED and not option_after_answer_reported:
                structural_errors.append(
                    "unexpected option line after ANSWER (options must appear before ANSWER)"
                )
                option_after_answer_reported = True
            label = cast(OptionLabel, om.group(1).upper())
            text = _extract_option_remainder(om)
            option_entries.append((label, [text] if text else []))
            if state != _BlockState.ANSWERED:
                state = _BlockState.OPTIONS
            continue

        if state == _BlockState.OPTIONS:
            um = UNSUPPORTED_OPTION_LINE.match(line)
            if um:
                in_unsupported_option = True
                bad_label = um.group(1).upper()
                if bad_label not in unsupported_seen:
                    unsupported_seen.add(bad_label)
                    unsupported_labels.append(bad_label)
                continue

        normalized_line = _normalize_whitespace(line)
        if state == _BlockState.STEM:
            question_parts.append(normalized_line)
        elif state == _BlockState.OPTIONS:
            # Multiline option continuation before next option/answer/question header.
            if not in_unsupported_option:
                option_entries[-1][1].append(normalized_line)
        else:
            # Never append trailing lines after ANSWER back into question_text.
            if not trailing_reported:
                structural_errors.append(
                    "unexpected trailing content after ANSWER (missing question header?)"
                )
                trailing_reported = True

    question_text = _normalize_whitespace(" ".join(question_parts))
    block_errors: list[str] = []
    if not question_text:
        block_errors.append("empty question text")

    preview_options, valid_option_map, distinct_labels, option_errors = _validate_options(
        option_entries, unsupported_labels
    )
    block_errors.extend(option_errors)
    block_errors.extend(structural_errors)

    if answer_count == 0:
        block_errors.append("missing answer (ANSWER: X)")
        answer_label = None
    else:
        block_errors.extend(answer_errors)
        if answer_label is not None:
            if answer_label not in distinct_labels:
                block_errors.append(
                    f"answer '{answer_label}' references an option that does not exist"
                )
                answer_label = None
            elif answer_label not in valid_option_map:
                # Referenced option existed only with empty text; do not keep invalid key.
                answer_label = None

    if option_after_answer_reported:
        answer_label = None

    is_valid = len(block_errors) == 0
    parsed_question = ParsedQuestion(
        question_text=question_text,
        position=block_index,
        options=preview_options,
        answer_label=answer_label,
        valid=is_valid,
        errors=block_errors,
    )
    error_models = [
        ParseQuestionsError(block_index=block_index, message=msg)
        for msg in block_errors
    ]
    return parsed_question, error_models


def parse_questions(raw_text: str) -> ParseQuestionsResponse:
    """Parse raw pasted question text into valid and invalid questions.

    Returns structured results so the admin can preview and correct parser
    problems before persisting anything.
    """
    if raw_text is None:
        err = ParseQuestionsError(
            block_index=0,
            message="empty input: no question blocks found",
        )
        return ParseQuestionsResponse(
            valid_questions=[],
            invalid_questions=[],
            errors=[err],
            total_blocks=0,
            valid_count=0,
            error_count=1,
        )

    normalized = _normalize_input(raw_text)
    if not normalized.strip():
        err = ParseQuestionsError(
            block_index=0,
            message="empty input: no question blocks found",
        )
        return ParseQuestionsResponse(
            valid_questions=[],
            invalid_questions=[],
            errors=[err],
            total_blocks=0,
            valid_count=0,
            error_count=1,
        )

    leading_orphan_lines, blocks = _segment_blocks(normalized.splitlines())
    all_errors: list[ParseQuestionsError] = []

    if not blocks:
        err = ParseQuestionsError(
            block_index=0,
            message=(
                "no question blocks found "
                "(expected numbered headers beginning with '1.', '1)', or 'Q1:')"
            ),
        )
        return ParseQuestionsResponse(
            valid_questions=[],
            invalid_questions=[],
            errors=[err],
            total_blocks=0,
            valid_count=0,
            error_count=1,
        )

    if leading_orphan_lines:
        all_errors.append(
            ParseQuestionsError(
                block_index=0,
                message=(
                    "unexpected content before first question header "
                    "(missing numbered marker such as '1.')"
                ),
            )
        )

    valid_questions: list[ParsedQuestion] = []
    invalid_questions: list[ParsedQuestion] = []

    for block_index, block_lines in enumerate(blocks, start=1):
        question, block_errors = _parse_and_validate_block(block_lines, block_index)
        if question.valid:
            valid_questions.append(question)
        else:
            invalid_questions.append(question)
            all_errors.extend(block_errors)

    return ParseQuestionsResponse(
        valid_questions=valid_questions,
        invalid_questions=invalid_questions,
        errors=all_errors,
        total_blocks=len(blocks),
        valid_count=len(valid_questions),
        error_count=len(all_errors),
    )


def parse_questions_with_answer_key(
    raw_text: str, answer_key_text: str | None = None
) -> ParseQuestionsResponse:
    """Apply a separate, explicitly numbered key before normal MCQ validation.

    Every question needs one matching key entry. Ambiguous, duplicate, extra,
    or conflicting entries invalidate the whole preview, so an inaccurate key
    can never be partially imported as ready questions. Work is O(N) in text
    size plus the number of blocks and key lines.
    """
    if not answer_key_text or not answer_key_text.strip():
        return parse_questions(raw_text)

    normalized = _normalize_input(raw_text)
    leading, blocks = _segment_blocks(normalized.splitlines())
    problems: list[str] = []
    key: dict[int, OptionLabel] = {}
    marks: dict[int, Decimal] = {}
    cleaned_key = _normalize_input(answer_key_text).strip()
    compact = re.fullmatch(r"[A-Da-d]+", re.sub(r"\s+", "", cleaned_key))
    if compact and not re.search(r"\d", cleaned_key):
        for number, letter in enumerate(compact.group().upper(), start=1):
            key[number] = cast(OptionLabel, letter)
    else:
        lines = [line.strip() for line in cleaned_key.splitlines() if line.strip()]
        for index in range(len(lines) - 2):
            if (
                re.fullmatch(r"\d+", lines[index])
                and re.fullmatch(r"[A-Da-d]", lines[index + 1])
                and re.fullmatch(r"\d+", lines[index + 2])
            ):
                number = int(lines[index])
                key[number] = cast(OptionLabel, lines[index + 1].upper())
                marks[number] = Decimal(lines[index + 2])
        for line in cleaned_key.splitlines():
            row = ANSWER_KEY_ROW.fullmatch(line)
            for match in ANSWER_KEY_ENTRY.finditer(line):
                number = int(match.group(1))
                letter = match.group(2).upper()
                if letter not in VALID_LABELS:
                    problems.append(
                        f"question {number} has invalid answer '{letter}' (expected A-D)"
                    )
                elif number in key:
                    problems.append(f"duplicate answer for question {number}")
                else:
                    key[number] = cast(OptionLabel, letter)
                    if row and row.group(3):
                        marks[number] = Decimal(row.group(3))

    numbered_blocks: list[int] = []
    for block in blocks:
        match = QUESTION_START.match(block[0])
        assert match is not None  # noqa: S101
        number = int(match.group(1) or match.group(5))
        if number in numbered_blocks:
            problems.append(f"duplicate question number {number}")
        numbered_blocks.append(number)
        if any(ANSWER_DIRECTIVE.match(line) for line in block[1:]):
            problems.append(
                f"question {number} has an inline answer; use one answer source only"
            )

    question_numbers = set(numbered_blocks)
    if len(key) != len(blocks):
        problems.append(
            f"Answer key has {len(key)} answers but {len(blocks)} questions were detected"
        )
    for number in sorted(question_numbers - key.keys()):
        problems.append(f"missing answer for question {number}")
    for number in sorted(key.keys() - question_numbers):
        problems.append(f"answer key references missing question {number}")

    if problems:
        preview = parse_questions(raw_text)
        message = "Correct the separate answer key before adding questions."
        all_questions = preview.valid_questions + preview.invalid_questions
        errors = list(preview.errors)
        errors.extend(ParseQuestionsError(block_index=0, message=item) for item in problems)
        for question in all_questions:
            question.answer_label = None
            question.valid = False
            question.errors.append(message)
            errors.append(ParseQuestionsError(block_index=question.position, message=message))
        return ParseQuestionsResponse(
            valid_questions=[],
            invalid_questions=all_questions,
            errors=errors,
            total_blocks=preview.total_blocks,
            valid_count=0,
            error_count=len(errors),
        )

    combined = "\n".join(leading)
    for number, block in zip(numbered_blocks, blocks, strict=True):
        combined += "\n" + "\n".join(block).rstrip() + f"\nANSWER: {key[number]}\n"
    preview = parse_questions(combined)
    for question in preview.valid_questions + preview.invalid_questions:
        question.points = marks.get(question.position, DEFAULT_POINTS)
    preview.normalized_answer_key = ", ".join(
        f"{number}. {key[number]}" for number in sorted(key)
    )
    if not preview.errors:
        return preview
    message = "Correct every question and answer before adding this keyed set."
    errors = list(preview.errors)
    for question in preview.valid_questions:
        question.valid = False
        question.answer_label = None
        question.errors.append(message)
        errors.append(ParseQuestionsError(block_index=question.position, message=message))
    return ParseQuestionsResponse(
        valid_questions=[],
        invalid_questions=sorted(
            preview.valid_questions + preview.invalid_questions,
            key=lambda question: question.position,
        ),
        errors=errors,
        total_blocks=preview.total_blocks,
        valid_count=0,
        error_count=len(errors),
    )
