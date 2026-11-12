"""Deterministic server-authoritative timer and MCQ grading engine.

RULE 22 — Literate Engineering Specification
============================================

Problem Statement
-----------------
Provide a single, pure, deterministic, server-authoritative engine for:
1. UTC examination deadline enforcement (`started_at`, `expires_at`, `is_expired`).
2. Deterministic `Decimal` multiple-choice grading from an attempt's frozen
   `AttemptQuestion` snapshot, `QuestionOption` answer key, and saved
   `StudentAnswer` selections.
3. Single idempotent finalization (`finalize_attempt_locked`) shared across
   manual submission (`STUDENT_SUBMITTED`) and timer expiry (`TIMER_EXPIRED`),
   preserving historical score immutability (`RULE 8`, `RULE 9`).
4. Post-submission answer-key disclosure gating (`RULE 10`) and truthful
   examination aggregate summaries (`compute_exam_results_summary`).

Domain Invariants
-----------------
* **Authoritative UTC Window:** `expires_at = ensure_utc(started_at) + timedelta(minutes=duration)`.
  Active iff `ensure_utc(now) < ensure_utc(expires_at)`; expired iff
  `ensure_utc(now) >= ensure_utc(expires_at)`. Answer mutations are rejected when
  expired, and browser clock/refresh cannot extend `expires_at`.
* **Single Terminal Transition & Score Immutability:** `finalize_attempt_locked`
  is the only transition into terminal `status = "GRADED"`. Once `status == "GRADED"`,
  `submitted_at`, `submission_reason`, and all persisted grade fields
  (`total_questions`, `correct_answers`, `incorrect_answers`,
  `unanswered_questions`, `points_earned`, `points_available`, `percentage`,
  `passed`) are immutable: subsequent finalizations immediately return
  `(attempt, False)` without recomputing or overwriting any column.
* **Count & Point Conservation:**
  - `total_questions == len(attempt_questions)`
  - `correct_answers + incorrect_answers + unanswered_questions == total_questions`
  - `Decimal("0.00") <= points_earned <= points_available` (both quantized `0.01`)
  - `Decimal("0.00") <= percentage <= Decimal("100.00")` (`ROUND_HALF_UP` to `0.01`)
  - `passed == (percentage >= quantize_two_places(pass_mark))`
* **Answer-Key Isolation (`RULE 10`):** `build_correct_map` and
  `build_question_review` (when `is_admin=False`) return answer keys strictly
  only when `attempt.status == "GRADED"` AND `exam.show_result is True` AND
  `exam.show_correct_answers is True`.

Assumptions & Edge Cases
------------------------
* **Timezone-Naive SQLite Datetimes:** SQLite test connections strip `tzinfo`
  from `DateTime(timezone=True)` columns. `ensure_utc` normalizes naive values
  as UTC and converts aware values via `.astimezone(UTC)` so comparisons never
  raise `TypeError`.
* **Zero Available Points:** If `total_questions == 0` or `points_available <= 0`,
  `percentage` evaluates safely to `Decimal("0.00")` without `ZeroDivisionError`.
* **Unanswered & Cleared Selections:** Missing `StudentAnswer` rows or rows
  with `selected_option_id=None` (explicitly cleared or `ON DELETE SET NULL`)
  count as `unanswered_questions += 1`.
* **Invalid / Stale Option IDs & Orphan Answers:** Any non-`None`
  `selected_option_id` not matching the question's single `is_correct=True`
  option counts as `incorrect_answers += 1` with `0.00` points. Answers for
  question IDs outside the frozen `AttemptQuestion` snapshot are ignored.
* **Multiple Correct Options Guard:** A question with more than one option
  marked `is_correct=True` fails closed with `ValueError`. A question with zero
  options marked `is_correct=True` yields `correct_option_id=None` so no
  selection can receive points.
* **Repeating & Midpoint Decimals:** All `Decimal` computations use exact
  base-10 arithmetic with `ROUND_HALF_UP` quantization to `0.01` (e.g., `1/3 -> 33.33`,
  `2/3 -> 66.67`, `12.345 -> 12.35`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.attempts.models import AttemptQuestion, ExamAttempt, StudentAnswer
from app.attempts.schemas import AttemptResult
from app.exams.models import Exam, Question

SubmissionReason = Literal["STUDENT_SUBMITTED", "TIMER_EXPIRED"]

VALID_SUBMISSION_REASONS: frozenset[str] = frozenset({"STUDENT_SUBMITTED", "TIMER_EXPIRED"})
FINALIZABLE_ATTEMPT_STATUSES: frozenset[str] = frozenset({"IN_PROGRESS", "SUBMITTED", "EXPIRED"})

TWO_PLACES = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class QuestionOutcome:
    """Deterministic per-question grading breakdown for a single attempt item."""

    question_id: UUID
    selected_option_id: UUID | None
    correct_option_id: UUID | None
    is_correct: bool
    points_earned: Decimal
    points_available: Decimal


@dataclass(frozen=True)
class GradeComputation:
    """Complete deterministic grading outcome across all snapshot questions."""

    total_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered_questions: int
    points_earned: Decimal
    points_available: Decimal
    percentage: Decimal
    passed: bool
    question_outcomes: list[QuestionOutcome]


def utc_now() -> datetime:
    """Return the current server UTC timestamp (timezone-aware)."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC-aware, treating naive values (e.g., SQLite) as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def compute_expires_at(started_at: datetime, duration_minutes: int) -> datetime:
    """Compute server-authoritative UTC expiration timestamp from duration."""
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    return ensure_utc(started_at) + timedelta(minutes=duration_minutes)


def is_expired(expires_at: datetime, *, now: datetime | None = None) -> bool:
    """Return True when the server UTC clock has reached or passed ``expires_at``."""
    current = ensure_utc(now if now is not None else utc_now())
    deadline = ensure_utc(expires_at)
    return current >= deadline


def resolve_submission_reason(
    expires_at: datetime,
    *,
    requested_reason: SubmissionReason = "STUDENT_SUBMITTED",
    now: datetime | None = None,
) -> SubmissionReason:
    """Return authoritative submission reason, forcing TIMER_EXPIRED at/after deadline."""
    if requested_reason not in VALID_SUBMISSION_REASONS:
        raise ValueError(f"Unsupported submission reason: {requested_reason!r}")
    if is_expired(expires_at, now=now):
        return "TIMER_EXPIRED"
    return requested_reason


def _to_uuid(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _quantize_two_places(value: Decimal | int | float | str) -> Decimal:
    dec = value if isinstance(value, Decimal) else Decimal(str(value))
    return dec.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _extract_question_id_and_points(item: Any) -> tuple[UUID, Decimal]:
    if isinstance(item, Mapping):
        raw_qid = item["question_id"]
        raw_points = item["points"]
    else:
        raw_qid = getattr(item, "question_id", None)
        if raw_qid is None:
            raw_qid = getattr(item, "id", None)
        if raw_qid is None:
            raise ValueError("Attempt question snapshot item is missing question_id")

        if hasattr(item, "points") and item.points is not None:
            raw_points = item.points
        elif getattr(item, "question", None) is not None and item.question.points is not None:
            raw_points = item.question.points
        else:
            raise ValueError(f"Question {raw_qid} is missing points")

    points = _quantize_two_places(raw_points)
    if points < ZERO:
        raise ValueError(f"Question {raw_qid} points cannot be negative: {points}")
    return _to_uuid(raw_qid), points


def _extract_option_id_and_correctness(option: Any) -> tuple[UUID, bool]:
    if isinstance(option, Mapping):
        raw_oid = option.get("id") or option.get("option_id")
        is_correct = bool(option.get("is_correct", False))
    else:
        raw_oid = getattr(option, "id", None)
        if raw_oid is None:
            raw_oid = getattr(option, "option_id", None)
        is_correct = bool(getattr(option, "is_correct", False))
    if raw_oid is None:
        raise ValueError("Question option is missing id")
    return _to_uuid(raw_oid), is_correct


def compute_mcq_grade(
    *,
    attempt_questions: Sequence[Any],
    options_by_question: Mapping[UUID, Sequence[Any]],
    answers_by_question: Mapping[UUID, UUID | None],
    pass_mark: Decimal,
) -> GradeComputation:
    """Compute deterministic MCQ grading across an attempt's frozen question snapshot."""
    normalized_pass_mark = _quantize_two_places(pass_mark)
    if normalized_pass_mark < ZERO or normalized_pass_mark > HUNDRED:
        raise ValueError(f"pass_mark must be between 0.00 and 100.00, got {normalized_pass_mark}")

    normalized_options: dict[UUID, Sequence[Any]] = {
        _to_uuid(qid): opts for qid, opts in options_by_question.items()
    }
    normalized_answers: dict[UUID, UUID | None] = {
        _to_uuid(qid): (_to_uuid(oid) if oid is not None else None)
        for qid, oid in answers_by_question.items()
    }

    seen_question_ids: set[UUID] = set()
    correct_answers = 0
    incorrect_answers = 0
    unanswered_questions = 0
    points_earned = ZERO
    points_available = ZERO
    question_outcomes: list[QuestionOutcome] = []

    for item in attempt_questions:
        question_id, q_points = _extract_question_id_and_points(item)
        if question_id in seen_question_ids:
            raise ValueError(f"Duplicate question_id in attempt snapshot: {question_id}")
        seen_question_ids.add(question_id)

        points_available += q_points

        question_options = normalized_options.get(question_id, ())
        correct_option_ids: list[UUID] = []
        for opt in question_options:
            opt_id, opt_is_correct = _extract_option_id_and_correctness(opt)
            if opt_is_correct:
                correct_option_ids.append(opt_id)

        if len(correct_option_ids) > 1:
            raise ValueError(
                f"Question {question_id} has multiple options marked as correct"
            )
        correct_option_id = correct_option_ids[0] if correct_option_ids else None

        selected_option_id = normalized_answers.get(question_id)
        if selected_option_id is None:
            unanswered_questions += 1
            is_correct = False
            earned_for_question = ZERO
        elif correct_option_id is not None and selected_option_id == correct_option_id:
            correct_answers += 1
            is_correct = True
            earned_for_question = q_points
            points_earned += q_points
        else:
            incorrect_answers += 1
            is_correct = False
            earned_for_question = ZERO

        question_outcomes.append(
            QuestionOutcome(
                question_id=question_id,
                selected_option_id=selected_option_id,
                correct_option_id=correct_option_id,
                is_correct=is_correct,
                points_earned=earned_for_question,
                points_available=q_points,
            )
        )

    points_earned = _quantize_two_places(points_earned)
    points_available = _quantize_two_places(points_available)

    if points_available > ZERO:
        percentage = ((points_earned / points_available) * HUNDRED).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
    else:
        percentage = ZERO

    passed = percentage >= normalized_pass_mark

    return GradeComputation(
        total_questions=len(question_outcomes),
        correct_answers=correct_answers,
        incorrect_answers=incorrect_answers,
        unanswered_questions=unanswered_questions,
        points_earned=points_earned,
        points_available=points_available,
        percentage=percentage,
        passed=passed,
        question_outcomes=question_outcomes,
    )


def _load_attempt_grading_inputs(
    db: Session,
    attempt_id: UUID,
) -> tuple[list[AttemptQuestion], dict[UUID, list[Any]], dict[UUID, UUID | None]]:
    aq_stmt = (
        select(AttemptQuestion)
        .where(AttemptQuestion.attempt_id == attempt_id)
        .options(
            selectinload(AttemptQuestion.question).selectinload(Question.options)
        )
        .order_by(AttemptQuestion.display_order)
    )
    attempt_questions = list(db.execute(aq_stmt).scalars().all())
    options_by_question: dict[UUID, list[Any]] = {
        _to_uuid(aq.question_id): list(aq.question.options)
        for aq in attempt_questions
    }

    ans_stmt = select(StudentAnswer).where(StudentAnswer.attempt_id == attempt_id)
    answers_by_question: dict[UUID, UUID | None] = {
        _to_uuid(ans.question_id): (
            _to_uuid(ans.selected_option_id) if ans.selected_option_id is not None else None
        )
        for ans in db.execute(ans_stmt).scalars().all()
    }
    return attempt_questions, options_by_question, answers_by_question


def finalize_attempt_locked(
    db: Session,
    attempt: ExamAttempt,
    exam: Exam,
    *,
    reason: SubmissionReason,
    now: datetime | None = None,
) -> tuple[ExamAttempt, bool]:
    """Finalize and grade an attempt once under the caller's row lock.

    Returns ``(attempt, False)`` immediately when ``attempt.status == "GRADED"``
    without mutating or recomputing any persisted column (score immutability).
    Otherwise grades the attempt deterministically, stamps terminal columns,
    flushes to the active transaction, and returns ``(attempt, True)``.
    """
    if reason not in VALID_SUBMISSION_REASONS:
        raise ValueError(f"Unsupported submission reason: {reason!r}")

    if attempt.status == "GRADED":
        return attempt, False

    if attempt.status not in FINALIZABLE_ATTEMPT_STATUSES:
        raise ValueError(f"Cannot finalize attempt in status {attempt.status!r}")

    if _to_uuid(attempt.exam_id) != _to_uuid(exam.id):
        raise ValueError("Attempt exam_id does not match provided exam")

    attempt_questions, options_by_question, answers_by_question = _load_attempt_grading_inputs(
        db, _to_uuid(attempt.id)
    )
    grade = compute_mcq_grade(
        attempt_questions=attempt_questions,
        options_by_question=options_by_question,
        answers_by_question=answers_by_question,
        pass_mark=exam.pass_mark,
    )

    finalized_at = ensure_utc(now if now is not None else utc_now())
    attempt.status = "GRADED"
    attempt.submission_reason = reason
    attempt.submitted_at = finalized_at
    attempt.updated_at = finalized_at
    attempt.total_questions = grade.total_questions
    attempt.correct_answers = grade.correct_answers
    attempt.incorrect_answers = grade.incorrect_answers
    attempt.unanswered_questions = grade.unanswered_questions
    attempt.points_earned = grade.points_earned
    attempt.points_available = grade.points_available
    attempt.percentage = grade.percentage
    attempt.passed = grade.passed

    db.add(attempt)
    db.flush()
    return attempt, True


def project_persisted_result(attempt: ExamAttempt) -> AttemptResult:
    """Project an immutable ``AttemptResult`` from persisted ``ExamAttempt`` columns."""
    if attempt.status != "GRADED":
        raise ValueError(f"Cannot project result for non-graded attempt ({attempt.status})")

    return AttemptResult(
        attempt_id=_to_uuid(attempt.id),
        exam_id=_to_uuid(attempt.exam_id),
        status=attempt.status,
        submission_reason=attempt.submission_reason,
        started_at=ensure_utc(attempt.started_at),
        expires_at=ensure_utc(attempt.expires_at),
        submitted_at=ensure_utc(attempt.submitted_at) if attempt.submitted_at is not None else None,
        total_questions=attempt.total_questions,
        correct_answers=attempt.correct_answers,
        incorrect_answers=attempt.incorrect_answers,
        unanswered_questions=attempt.unanswered_questions,
        points_earned=_quantize_two_places(attempt.points_earned),
        points_available=_quantize_two_places(attempt.points_available),
        percentage=_quantize_two_places(attempt.percentage),
        passed=bool(attempt.passed),
    )


def can_view_student_result(attempt: ExamAttempt, exam: Exam) -> bool:
    """Return True iff student score/result details may be disclosed."""
    return attempt.status == "GRADED" and bool(exam.show_result)


def can_view_correct_answers(attempt: ExamAttempt, exam: Exam) -> bool:
    """Return True iff post-submission correct-answer review may be disclosed."""
    return (
        attempt.status == "GRADED"
        and bool(exam.show_result)
        and bool(exam.show_correct_answers)
    )


def build_correct_map(
    db: Session,
    attempt: ExamAttempt,
    exam: Exam | None = None,
) -> dict[UUID, UUID | None]:
    """Return ``{question_id: correct_option_id}`` strictly after finalization when allowed.

    Enforces ``RULE 10`` fail-closed: returns an empty dictionary unless
    ``attempt.status == "GRADED"`` AND ``exam.show_result`` AND
    ``exam.show_correct_answers``.
    """
    if attempt.status != "GRADED":
        return {}

    resolved_exam = exam if exam is not None else db.get(Exam, _to_uuid(attempt.exam_id))
    if resolved_exam is None:
        return {}
    if _to_uuid(resolved_exam.id) != _to_uuid(attempt.exam_id):
        raise ValueError("Attempt exam_id does not match provided exam")
    if not can_view_correct_answers(attempt, resolved_exam):
        return {}

    aq_stmt = (
        select(AttemptQuestion)
        .where(AttemptQuestion.attempt_id == _to_uuid(attempt.id))
        .options(selectinload(AttemptQuestion.question).selectinload(Question.options))
        .order_by(AttemptQuestion.display_order)
    )
    attempt_questions = list(db.execute(aq_stmt).scalars().all())

    correct_map: dict[UUID, UUID | None] = {}
    for aq in attempt_questions:
        qid = _to_uuid(aq.question_id)
        correct_ids = [
            _to_uuid(opt.id) for opt in aq.question.options if bool(opt.is_correct)
        ]
        if len(correct_ids) > 1:
            raise ValueError(f"Question {qid} has multiple options marked as correct")
        correct_map[qid] = correct_ids[0] if correct_ids else None
    return correct_map


def build_question_review(
    db: Session,
    attempt: ExamAttempt,
    exam: Exam | None = None,
    *,
    is_admin: bool = False,
) -> list[QuestionOutcome] | None:
    """Return ordered per-question outcomes post-submission when authorized.

    Returns ``None`` unless ``attempt.status == "GRADED"`` and either
    ``is_admin=True`` or (``exam.show_result`` and ``exam.show_correct_answers``).
    """
    if attempt.status != "GRADED":
        return None

    resolved_exam = exam if exam is not None else db.get(Exam, _to_uuid(attempt.exam_id))
    if resolved_exam is None:
        return None
    if _to_uuid(resolved_exam.id) != _to_uuid(attempt.exam_id):
        raise ValueError("Attempt exam_id does not match provided exam")

    if not is_admin and not can_view_correct_answers(attempt, resolved_exam):
        return None

    attempt_questions, options_by_question, answers_by_question = _load_attempt_grading_inputs(
        db, _to_uuid(attempt.id)
    )
    grade = compute_mcq_grade(
        attempt_questions=attempt_questions,
        options_by_question=options_by_question,
        answers_by_question=answers_by_question,
        pass_mark=resolved_exam.pass_mark,
    )
    return grade.question_outcomes


def compute_exam_results_summary(
    attempts: Sequence[ExamAttempt],
) -> dict[str, int | Decimal | None]:
    """Aggregate truthful summary metrics over completed (GRADED) attempts."""
    completed = [attempt for attempt in attempts if attempt.status == "GRADED"]
    if not completed:
        return {
            "completed_attempts": 0,
            "average_percentage": None,
            "highest_percentage": None,
            "lowest_percentage": None,
            "pass_rate": None,
        }

    percentages = [_quantize_two_places(attempt.percentage) for attempt in completed]
    completed_count = Decimal(len(completed))
    average_percentage = (sum(percentages, ZERO) / completed_count).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    passed_count = sum(1 for attempt in completed if bool(attempt.passed))
    pass_rate = ((Decimal(passed_count) / completed_count) * HUNDRED).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    return {
        "completed_attempts": len(completed),
        "average_percentage": average_percentage,
        "highest_percentage": max(percentages),
        "lowest_percentage": min(percentages),
        "pass_rate": pass_rate,
    }
