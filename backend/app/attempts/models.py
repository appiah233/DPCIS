"""Attempt and grading domain SQLAlchemy models.

Defines ``exam_attempts``, ``attempt_questions``, and ``student_answers``
tables. These freeze the server-authoritative state of each student sitting so
the examination can be reproduced exactly as delivered, graded deterministically
on the backend, and stored immutably.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import conv

from app.database.base import Base

if TYPE_CHECKING:
    from app.exams.models import Exam, Question


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    exam_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("application_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="IN_PROGRESS",
        server_default=text("'IN_PROGRESS'"),
    )
    submission_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_answers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    incorrect_answers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    unanswered_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    points_earned: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    points_available: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    exam: Mapped[Exam] = relationship("Exam", back_populates="attempts")
    attempt_questions: Mapped[list[AttemptQuestion]] = relationship(
        "AttemptQuestion",
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="AttemptQuestion.display_order",
    )
    answers: Mapped[list[StudentAnswer]] = relationship(
        "StudentAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'SUBMITTED', 'EXPIRED', 'GRADED')",
            name=conv("ck_exam_attempts_status"),
        ),
        CheckConstraint(
            "submission_reason IS NULL OR "
            "submission_reason IN ('STUDENT_SUBMITTED', 'TIMER_EXPIRED')",
            name=conv("ck_exam_attempts_submission_reason"),
        ),
        CheckConstraint(
            "total_questions >= 0",
            name=conv("ck_exam_attempts_total_questions_nonneg"),
        ),
        CheckConstraint(
            "points_available >= 0",
            name=conv("ck_exam_attempts_points_available_nonneg"),
        ),
        CheckConstraint(
            "points_earned >= 0",
            name=conv("ck_exam_attempts_points_earned_nonneg"),
        ),
        CheckConstraint(
            "percentage >= 0 AND percentage <= 100",
            name=conv("ck_exam_attempts_percentage_range"),
        ),
        Index("ix_exam_attempts_user_id_exam_id", "user_id", "exam_id"),
        Index("ix_exam_attempts_exam_id_status", "exam_id", "status"),
        Index(
            "uq_exam_attempts_active_user_exam",
            "user_id",
            "exam_id",
            unique=True,
            postgresql_where=text("status = 'IN_PROGRESS'"),
            sqlite_where=text("status = 'IN_PROGRESS'"),
        ),
    )


class AttemptQuestion(Base):
    __tablename__ = "attempt_questions"

    attempt_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("exam_attempts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    option_order: Mapped[str | None] = mapped_column(Text, nullable=True)

    attempt: Mapped[ExamAttempt] = relationship("ExamAttempt", back_populates="attempt_questions")
    question: Mapped[Question] = relationship("Question", back_populates="attempt_links")

    __table_args__ = (
        CheckConstraint(
            "display_order >= 0",
            name=conv("ck_attempt_questions_display_order_nonneg"),
        ),
        Index(
            "uq_attempt_questions_attempt_id_display_order",
            "attempt_id",
            "display_order",
            unique=True,
        ),
    )


class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    attempt_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("exam_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    selected_option_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("question_options.id", ondelete="SET NULL"),
        nullable=True,
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    attempt: Mapped[ExamAttempt] = relationship("ExamAttempt", back_populates="answers")
    question: Mapped[Question] = relationship("Question", back_populates="answers")

    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_student_answers_attempt_id_question_id",
        ),
        Index("ix_student_answers_attempt_id", "attempt_id"),
    )
