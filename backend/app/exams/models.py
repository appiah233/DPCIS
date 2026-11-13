"""Examination domain SQLAlchemy models.

Defines ``exams``, ``questions``, and ``question_options`` tables. These are
application-owned tables stored in the same PostgreSQL database as
``application_users``. Neon Managed Auth schema is never touched.
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
    from app.attempts.models import AttemptQuestion, ExamAttempt, StudentAnswer


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    pass_mark: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    question_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    randomize_questions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    randomize_options: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    show_result: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sa.true(),
    )
    show_correct_answers: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="DRAFT",
        server_default=text("'DRAFT'"),
    )
    created_by: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("application_users.id"),
        nullable=False,
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
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions: Mapped[list[Question]] = relationship(
        "Question",
        back_populates="exam",
        cascade="all, delete-orphan",
        order_by="Question.position",
    )
    attempts: Mapped[list[ExamAttempt]] = relationship(
        "ExamAttempt",
        back_populates="exam",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "duration_minutes > 0",
            name=conv("ck_exams_duration_minutes_positive"),
        ),
        CheckConstraint(
            "pass_mark >= 0 AND pass_mark <= 100",
            name=conv("ck_exams_pass_mark_range"),
        ),
        CheckConstraint(
            "question_limit IS NULL OR question_limit > 0",
            name=conv("ck_exams_question_limit_positive"),
        ),
        CheckConstraint(
            "max_attempts >= 1",
            name=conv("ck_exams_max_attempts_positive"),
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'CLOSED')",
            name=conv("ck_exams_status"),
        ),
        Index("ix_exams_status", "status"),
        Index("ix_exams_created_by", "created_by"),
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    exam_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("exam_source_files.id"), nullable=True
    )
    source_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_regions: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_paths: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_options_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("1.00"),
        server_default=text("1.00"),
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

    exam: Mapped[Exam] = relationship("Exam", back_populates="questions")
    options: Mapped[list[QuestionOption]] = relationship(
        "QuestionOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.position",
    )
    attempt_links: Mapped[list[AttemptQuestion]] = relationship(
        "AttemptQuestion",
        back_populates="question",
        cascade="all, delete-orphan",
    )
    answers: Mapped[list[StudentAnswer]] = relationship(
        "StudentAnswer",
        back_populates="question",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("points > 0", name=conv("ck_questions_points_positive")),
        Index("ix_questions_exam_id_position", "exam_id", "position"),
    )


class ExamSourceFile(Base):
    __tablename__ = "exam_source_files"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    exam_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_exam_source_files_exam_id", "exam_id"),)


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(1), nullable=False)
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[Question] = relationship("Question", back_populates="options")

    __table_args__ = (
        UniqueConstraint("question_id", "label", name="uq_question_options_question_id_label"),
        CheckConstraint(
            "label IN ('A', 'B', 'C', 'D')",
            name=conv("ck_question_options_label_valid"),
        ),
        Index("ix_question_options_question_id", "question_id"),
        Index(
            "uq_question_options_one_correct_per_question",
            "question_id",
            unique=True,
            postgresql_where=text("is_correct IS TRUE"),
            sqlite_where=text("is_correct = 1"),
        ),
    )
