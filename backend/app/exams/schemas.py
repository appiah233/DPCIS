"""Pydantic schemas for the examination authoring and student listing domain.

Schemas are strictly separated into admin-facing (exposes configuration,
lifecycle timestamps, and answer keys via ``is_correct``) and student-facing
(exposes published exam metadata and availability only; never exposes
questions, options, or answer-key fields).
"""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OptionLabel = Literal["A", "B", "C", "D"]
ExamStatus = Literal["DRAFT", "PUBLISHED", "CLOSED"]
VALID_OPTION_LABELS: tuple[OptionLabel, ...] = ("A", "B", "C", "D")

_NON_NULLABLE_EXAM_UPDATE_FIELDS: tuple[str, ...] = (
    "title",
    "duration_minutes",
    "pass_mark",
    "randomize_questions",
    "randomize_options",
    "max_attempts",
    "show_result",
    "show_correct_answers",
)


def _strip_required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned


def _strip_optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("value must be a string")
    cleaned = value.strip()
    return cleaned or None


def _reject_bool_numeric(value: object, *, field_name: str) -> object:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number, not a boolean")
    return value


def _coerce_finite_decimal(value: object, *, field_name: str) -> Decimal:
    _reject_bool_numeric(value, field_name=field_name)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid decimal number") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be a finite number")
    return parsed


def _normalize_option_text_for_dup_check(text: str) -> str:
    return " ".join(text.split()).casefold()


# ---------------------------------------------------------------------------
# Shared & admin question option schemas
# ---------------------------------------------------------------------------


class QuestionOptionBase(BaseModel):
    label: OptionLabel
    option_text: str = Field(min_length=1)

    @field_validator("option_text", mode="before")
    @classmethod
    def _validate_option_text(cls, value: object) -> str:
        return _strip_required_text(value, field_name="option_text")


class QuestionOptionCreate(QuestionOptionBase):
    """Admin-authored option payload including answer-key flag."""

    is_correct: bool = False


class QuestionOptionAdminOut(QuestionOptionBase):
    """Admin-facing option: includes id, position, and is_correct."""

    id: UUID | None = None
    is_correct: bool = False
    position: int = Field(default=0, ge=0)

    model_config = ConfigDict(from_attributes=True)


# Backwards-compatible alias for existing imports.
QuestionOptionAdmin = QuestionOptionAdminOut


# ---------------------------------------------------------------------------
# Exam schemas
# ---------------------------------------------------------------------------


class ExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=4000)
    duration_minutes: int = Field(ge=1)
    pass_mark: Decimal = Field(
        default=Decimal("50.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=5,
        decimal_places=2,
    )
    question_limit: int | None = Field(default=None, ge=1)
    randomize_questions: bool = False
    randomize_options: bool = False
    max_attempts: int = Field(default=1, ge=1)
    show_result: bool = True
    show_correct_answers: bool = False

    @field_validator("title", mode="before")
    @classmethod
    def _validate_title(cls, value: object) -> str:
        return _strip_required_text(value, field_name="title")

    @field_validator("description", "instructions", mode="before")
    @classmethod
    def _validate_optional_text(cls, value: object) -> str | None:
        return _strip_optional_text(value)

    @field_validator("duration_minutes", "max_attempts", "question_limit", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: object, info) -> object:
        if value is None:
            return None
        return _reject_bool_numeric(value, field_name=info.field_name)

    @field_validator("pass_mark", mode="before")
    @classmethod
    def _coerce_pass_mark(cls, value: object) -> Decimal:
        return _coerce_finite_decimal(value, field_name="pass_mark")


class ExamUpdate(BaseModel):
    """Partial draft update payload. Status changes are disallowed here."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=4000)
    duration_minutes: int | None = Field(default=None, ge=1)
    pass_mark: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=5,
        decimal_places=2,
    )
    question_limit: int | None = Field(default=None, ge=1)
    randomize_questions: bool | None = None
    randomize_options: bool | None = None
    max_attempts: int | None = Field(default=None, ge=1)
    show_result: bool | None = None
    show_correct_answers: bool | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _validate_title(cls, value: object) -> str | None:
        if value is None:
            return None
        return _strip_required_text(value, field_name="title")

    @field_validator("description", "instructions", mode="before")
    @classmethod
    def _validate_optional_text(cls, value: object) -> str | None:
        return _strip_optional_text(value)

    @field_validator("duration_minutes", "max_attempts", "question_limit", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: object, info) -> object:
        if value is None:
            return None
        return _reject_bool_numeric(value, field_name=info.field_name)

    @field_validator("pass_mark", mode="before")
    @classmethod
    def _coerce_pass_mark(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        return _coerce_finite_decimal(value, field_name="pass_mark")

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> ExamUpdate:
        for field_name in _NON_NULLABLE_EXAM_UPDATE_FIELDS:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class ExamAdminOut(BaseModel):
    """Full admin view of an exam, including answer-key-relevant config."""

    id: UUID
    title: str
    description: str | None
    instructions: str | None
    duration_minutes: int
    pass_mark: Decimal
    question_limit: int | None
    randomize_questions: bool
    randomize_options: bool
    max_attempts: int
    show_result: bool
    show_correct_answers: bool
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    closed_at: datetime | None
    question_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ExamWithQuestionsAdmin(ExamAdminOut):
    """Admin view including questions and options (with is_correct)."""

    questions: list[QuestionAdminOut] = Field(default_factory=list)


class ExamStudentOut(BaseModel):
    """Student-facing exam view: metadata and availability only, never answer keys."""

    id: UUID
    title: str
    description: str | None
    instructions: str | None
    duration_minutes: int
    pass_mark: Decimal
    question_limit: int | None
    randomize_questions: bool
    randomize_options: bool
    max_attempts: int
    show_result: bool
    question_count: int = 0
    attempts_used: int = 0
    active_attempt_id: UUID | None = None
    can_start: bool = True
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


ExamStudentListItem = ExamStudentOut


class ExamPublish(BaseModel):
    """Explicit publish request body."""

    pass


# ---------------------------------------------------------------------------
# Question schemas (admin)
# ---------------------------------------------------------------------------


class QuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    position: int | None = Field(default=None, ge=0)
    points: Decimal = Field(
        default=Decimal("1.00"),
        gt=Decimal("0"),
        le=Decimal("999.99"),
        max_digits=5,
        decimal_places=2,
    )
    options: list[QuestionOptionCreate] = Field(min_length=2, max_length=4)

    @field_validator("question_text", mode="before")
    @classmethod
    def _validate_question_text(cls, value: object) -> str:
        return _strip_required_text(value, field_name="question_text")

    @field_validator("position", mode="before")
    @classmethod
    def _validate_position_not_bool(cls, value: object) -> object:
        if value is None:
            return None
        return _reject_bool_numeric(value, field_name="position")

    @field_validator("points", mode="before")
    @classmethod
    def _coerce_points(cls, value: object) -> Decimal:
        return _coerce_finite_decimal(value, field_name="points")

    @model_validator(mode="after")
    def _validate_options_and_answer_key(self) -> QuestionCreate:
        labels = [o.label for o in self.options]
        if len(set(labels)) != len(labels):
            raise ValueError("option labels must be unique within a question")

        expected_labels = list(VALID_OPTION_LABELS[: len(self.options)])
        if labels != expected_labels:
            raise ValueError(
                "options must have sequential labels starting at 'A' without gaps"
            )

        seen_texts: set[str] = set()
        for option in self.options:
            normalized = _normalize_option_text_for_dup_check(option.option_text)
            if normalized in seen_texts:
                raise ValueError("option texts must be distinct within a question")
            seen_texts.add(normalized)

        correct = [o for o in self.options if o.is_correct]
        if len(correct) != 1:
            raise ValueError("each question must have exactly one correct answer")
        return self


class SaveQuestionsRequest(BaseModel):
    """Optional wrapper object for bulk question replacement."""

    model_config = ConfigDict(extra="forbid")

    questions: list[QuestionCreate]


class QuestionAdminOut(BaseModel):
    id: UUID
    question_text: str
    position: int
    points: Decimal
    options: list[QuestionOptionAdminOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Question parsing
# ---------------------------------------------------------------------------


class ParsedOption(QuestionOptionBase):
    """Parsed MCQ option preview item (label A-D and non-empty text)."""


class ParsedQuestion(BaseModel):
    question_text: str
    position: int
    points: Decimal = Decimal("1.00")
    options: list[ParsedOption]
    answer_label: OptionLabel | None = None
    valid: bool = True
    errors: list[str] = Field(default_factory=list)


class ParseQuestionsRequest(BaseModel):
    raw_text: str


class ParseQuestionsError(BaseModel):
    block_index: int
    message: str


class ParseQuestionsResponse(BaseModel):
    valid_questions: list[ParsedQuestion]
    invalid_questions: list[ParsedQuestion]
    errors: list[ParseQuestionsError]
    total_blocks: int = 0
    valid_count: int = 0
    error_count: int = 0


ExamWithQuestionsAdmin.model_rebuild()
