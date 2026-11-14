"""Pydantic schemas for the student attempt, delivery, autosave, and results domain.

Student-facing active schemas strictly exclude answer-key fields
(``is_correct``, ``correct_option_id``) and authoritative grading fields.
Post-submission schemas disclose scores and question-level answer keys only
when permitted by ``exam.show_result`` and ``exam.show_correct_answers``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

OptionLabel = Literal["A", "B", "C", "D"]


# ---------------------------------------------------------------------------
# Start / resume attempt
# ---------------------------------------------------------------------------


class AttemptStartRequest(BaseModel):
    """Empty optional start payload; forbids client tampering fields."""

    model_config = ConfigDict(extra="forbid")


class AttemptStartResponse(BaseModel):
    """Server-authoritative start/resume confirmation payload."""

    attempt_id: UUID
    exam_id: UUID
    status: str
    started_at: datetime
    expires_at: datetime
    server_now: datetime
    total_questions: int
    duration_minutes: int
    resumed: bool = False

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Active attempt delivery (student-facing, zero answer keys)
# ---------------------------------------------------------------------------


class AttemptOptionDelivery(BaseModel):
    """An option delivered to a student: strictly excludes ``is_correct``."""

    id: UUID
    label: OptionLabel
    option_text: str

    model_config = ConfigDict(from_attributes=True)


class AttemptQuestionDelivery(BaseModel):
    """A frozen-order question delivered during an active attempt."""

    id: UUID
    display_order: int
    question_text: str
    image_urls: list[str] = Field(default_factory=list)
    points: Decimal
    options: list[AttemptOptionDelivery] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AttemptDelivery(BaseModel):
    """Full active sitting snapshot including deadline and saved answers."""

    attempt_id: UUID
    exam_id: UUID
    exam_title: str
    duration_minutes: int
    status: str
    started_at: datetime
    expires_at: datetime
    server_now: datetime
    total_questions: int
    questions: list[AttemptQuestionDelivery]
    saved_answers: dict[UUID, UUID | None] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Autosave answer
# ---------------------------------------------------------------------------


class AnswerSaveRequest(BaseModel):
    """Strict autosave payload: only ``selected_option_id`` may be sent."""

    model_config = ConfigDict(extra="forbid")

    selected_option_id: UUID | None = None


class AnswerSaveResponse(BaseModel):
    """Persisted autosave confirmation (never exposes ``is_correct``)."""

    attempt_id: UUID
    question_id: UUID
    selected_option_id: UUID | None
    answered_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Submission & grading results
# ---------------------------------------------------------------------------


class AttemptSubmitRequest(BaseModel):
    """Strict submission payload: forbids client-supplied score fields."""

    model_config = ConfigDict(extra="forbid")

    confirm: bool = Field(default=True)


class AttemptResult(BaseModel):
    """Core persisted grading projection returned by ``grading.py``."""

    attempt_id: UUID
    exam_id: UUID
    status: str
    submission_reason: str | None
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered_questions: int
    points_earned: Decimal
    points_available: Decimal
    percentage: Decimal
    passed: bool

    model_config = ConfigDict(from_attributes=True)


class AttemptQuestionReviewOption(BaseModel):
    """Post-submission option review item (exposed only when authorized)."""

    id: UUID
    label: OptionLabel
    option_text: str
    is_correct: bool

    model_config = ConfigDict(from_attributes=True)


class AttemptQuestionReviewItem(BaseModel):
    """Post-submission per-question breakdown (exposed only when authorized)."""

    question_id: UUID
    display_order: int
    question_text: str
    selected_option_id: UUID | None
    correct_option_id: UUID | None
    is_correct: bool
    points_earned: Decimal
    points_available: Decimal
    options: list[AttemptQuestionReviewOption] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AttemptResultOut(BaseModel):
    """Disclosed attempt result for authorized student or admin inspection."""

    attempt_id: UUID
    exam_id: UUID
    exam_title: str
    status: str
    submission_reason: str | None
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered_questions: int
    points_earned: Decimal
    points_available: Decimal
    percentage: Decimal
    pass_mark: Decimal
    passed: bool
    result_visible: Literal[True] = True
    show_correct_answers: bool
    question_review: list[AttemptQuestionReviewItem] | None = None
    student_user_id: UUID | None = None
    student_email: str | None = None
    student_display_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AttemptSubmittedHiddenOut(BaseModel):
    """Finalized attempt acknowledgment when ``exam.show_result`` is False."""

    attempt_id: UUID
    exam_id: UUID
    exam_title: str
    status: str
    submission_reason: str | None
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    total_questions: int
    result_visible: Literal[False] = False
    show_correct_answers: Literal[False] = False
    message: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Student attempt history
# ---------------------------------------------------------------------------


class StudentAttemptSummary(BaseModel):
    """Student-owned attempt summary across examinations."""

    attempt_id: UUID
    exam_id: UUID
    exam_title: str
    status: str
    submission_reason: str | None
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    total_questions: int
    result_visible: bool
    points_earned: Decimal | None = None
    points_available: Decimal | None = None
    percentage: Decimal | None = None
    passed: bool | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Admin result views
# ---------------------------------------------------------------------------


class ExamAdminAttemptRow(BaseModel):
    """Single student attempt row for administrator results oversight."""

    attempt_id: UUID
    user_id: UUID
    email: str | None
    display_name: str | None
    status: str
    submission_reason: str | None
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered_questions: int
    points_earned: Decimal
    points_available: Decimal
    percentage: Decimal
    passed: bool

    model_config = ConfigDict(from_attributes=True)


# Backwards-compatible alias for earlier drafts.
AttemptAdminResult = ExamAdminAttemptRow


class ExamResultsSummary(BaseModel):
    """Aggregate metrics over completed (GRADED) attempts for an examination."""

    completed_attempts: int
    average_percentage: Decimal | None
    highest_percentage: Decimal | None
    lowest_percentage: Decimal | None
    pass_rate: Decimal | None

    model_config = ConfigDict(from_attributes=True)


class ExamAdminResultsResponse(BaseModel):
    """Administrator examination results overview combining summary and rows."""

    exam_id: UUID
    exam_title: str
    pass_mark: Decimal
    total_attempts: int
    summary: ExamResultsSummary
    attempts: list[ExamAdminAttemptRow] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
