"""Student attempt lifecycle, delivery, autosave, and results service layer.

RULE 22 — Literate Engineering Specification
============================================

Problem
-------
Provide a concurrency-safe, server-authoritative service layer managing student
examination sittings from eligibility verification through frozen-snapshot
delivery, idempotent autosave, submission/result disclosure, student history,
and administrator results oversight.

Invariants
----------
1. **Authoritative Actor Identity:** Every student and admin operation keys on
   ``identity.user_id`` (``application_users.id`` UUID), never raw
   ``identity.subject`` or client-supplied user IDs.
2. **Eligibility & Idempotent Start/Resume:** Only ``PUBLISHED`` exams with
   questions may be started. Before inspecting quota, any expired
   ``IN_PROGRESS`` attempt for ``(student_user_id, exam_id)`` is lazily
   finalized via ``finalize_attempt_locked(..., reason="TIMER_EXPIRED")``. An
   unexpired ``IN_PROGRESS`` attempt is resumed idempotently with identical
   ``attempt_id``, ``started_at``, ``expires_at``, question order, and option
   order.
3. **Frozen Snapshot & Normalized Labels:** At attempt creation, selected
   questions are frozen in ``attempt_questions.display_order`` and every
   question's option UUID order is frozen as JSON in
   ``attempt_questions.option_order`` (shuffled once when
   ``randomize_options=True``, positional otherwise). Delivery emits options in
   the frozen order with sequential labels ``"A"``–``"D"`` while keeping option
   UUIDs canonical for autosave and grading.
4. **Answer-Key & Score Isolation (``RULE 9``, ``RULE 10``):** Active delivery
   and autosave never accept client scores or expose ``is_correct``,
   ``correct_option_id``, or ``pass_mark``. Post-submission results withhold
   numeric scores when ``exam.show_result=False`` and withhold question-level
   answer keys unless ``attempt.status == "GRADED"`` and
   ``exam.show_correct_answers=True`` (or ``is_admin=True``).
5. **Concurrency & Race Protection:**
   - ``start_attempt`` locks the caller's ``application_users`` row
     (``FOR UPDATE``) and handles ``IntegrityError`` from
     ``uq_exam_attempts_active_user_exam`` cleanly so multi-tab starts never
     create duplicate active attempts or bypass ``max_attempts``.
   - ``save_answer``, ``submit_attempt``, and lazy expiry lock the target
     ``exam_attempts`` row (``FOR UPDATE``) before checking status/deadline,
     preventing save-vs-submit and timer-vs-submit races.
   - ``save_answer`` performs a dialect-safe atomic ``ON CONFLICT DO UPDATE``
     upsert on ``(attempt_id, question_id)``.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Sequence
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import cast
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.attempts import models as attempt_models
from app.attempts.grading import (
    SubmissionReason,
    build_question_review,
    can_view_correct_answers,
    can_view_student_result,
    compute_exam_results_summary,
    compute_expires_at,
    ensure_utc,
    finalize_attempt_locked,
    is_expired,
    project_persisted_result,
    resolve_submission_reason,
    utc_now,
)
from app.attempts.schemas import (
    AnswerSaveResponse,
    AttemptDelivery,
    AttemptOptionDelivery,
    AttemptQuestionDelivery,
    AttemptQuestionReviewItem,
    AttemptQuestionReviewOption,
    AttemptResultOut,
    AttemptStartResponse,
    AttemptSubmittedHiddenOut,
    ExamAdminAttemptRow,
    ExamAdminResultsResponse,
    ExamResultsSummary,
    OptionLabel,
    StudentAttemptSummary,
)
from app.auth.dependencies import ROLE_ADMIN, ROLE_STUDENT, AuthIdentity
from app.exams import models as exam_models
from app.users.models import ApplicationUser

VALID_OPTION_LABELS: tuple[OptionLabel, ...] = ("A", "B", "C", "D")
TWO_PLACES = Decimal("0.01")
_SYSTEM_RANDOM = secrets.SystemRandom()


class AttemptConflictException(HTTPException):
    """HTTP 409 conflict carrying structured attempt state metadata."""

    def __init__(
        self,
        *,
        detail: str,
        code: str,
        attempt_id: UUID,
        attempt_status: str,
    ) -> None:
        self.error_payload: dict[str, str] = {
            "detail": detail,
            "code": code,
            "attempt_id": str(attempt_id),
            "status": attempt_status,
        }
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def require_student_user_id(identity: AuthIdentity) -> UUID:
    """Fail-closed check returning the student's ``application_users.id`` UUID."""
    if identity.role is not None and identity.role != ROLE_STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student role required",
        )
    if identity.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Application identity not established",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if identity.role != ROLE_STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student role required",
        )
    return identity.user_id


def require_admin_user_id(identity: AuthIdentity) -> UUID:
    """Fail-closed check returning the admin's ``application_users.id`` UUID."""
    if identity.role is not None and identity.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    if identity.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Application identity not established",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if identity.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return identity.user_id


def _serialize_option_order(options: Sequence[exam_models.QuestionOption]) -> str:
    return json.dumps([str(opt.id) for opt in options])


def _parse_option_order(raw_order: str | None) -> list[UUID]:
    if not raw_order:
        return []
    cleaned = raw_order.strip()
    if not cleaned:
        return []
    if cleaned.startswith("["):
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [UUID(str(item)) for item in parsed]
        return []
    return [UUID(part.strip()) for part in cleaned.split(",") if part.strip()]


def _order_options_by_snapshot(
    options: Sequence[exam_models.QuestionOption],
    raw_option_order: str | None,
) -> list[exam_models.QuestionOption]:
    ordered_ids = _parse_option_order(raw_option_order)
    if not ordered_ids:
        return sorted(options, key=lambda opt: (opt.position, opt.id))

    rank = {option_id: idx for idx, option_id in enumerate(ordered_ids)}
    fallback_base = len(rank)
    return sorted(
        options,
        key=lambda opt: (
            0 if opt.id in rank else 1,
            rank.get(opt.id, fallback_base),
            opt.position,
            opt.id,
        ),
    )


def _load_attempt_for_student(
    db: Session,
    *,
    attempt_id: UUID,
    student_user_id: UUID,
    for_update: bool = False,
) -> attempt_models.ExamAttempt:
    stmt = select(attempt_models.ExamAttempt).where(
        attempt_models.ExamAttempt.id == attempt_id
    )
    if for_update:
        stmt = stmt.with_for_update()
    attempt = db.execute(stmt).scalar_one_or_none()
    if attempt is None or attempt.user_id != student_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found",
        )
    return attempt


def _load_exam_or_404(db: Session, exam_id: UUID) -> exam_models.Exam:
    exam = db.get(exam_models.Exam, exam_id)
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination not found",
        )
    return exam


def _finalize_expired_attempt_in_tx(
    db: Session,
    *,
    attempt_id: UUID,
    exam: exam_models.Exam,
    now: datetime,
) -> attempt_models.ExamAttempt:
    locked = db.execute(
        select(attempt_models.ExamAttempt)
        .where(attempt_models.ExamAttempt.id == attempt_id)
        .with_for_update()
    ).scalar_one()
    if locked.status == "IN_PROGRESS" and is_expired(locked.expires_at, now=now):
        finalize_attempt_locked(
            db,
            locked,
            exam,
            reason="TIMER_EXPIRED",
            now=now,
        )
        db.commit()
        db.refresh(locked)
    return locked


def _build_question_review_items(
    db: Session,
    *,
    attempt: attempt_models.ExamAttempt,
    exam: exam_models.Exam,
    is_admin: bool,
) -> list[AttemptQuestionReviewItem] | None:
    outcomes = build_question_review(db, attempt, exam, is_admin=is_admin)
    if outcomes is None:
        return None

    aq_rows = list(
        db.execute(
            select(attempt_models.AttemptQuestion)
            .where(attempt_models.AttemptQuestion.attempt_id == attempt.id)
            .options(
                selectinload(attempt_models.AttemptQuestion.question).selectinload(
                    exam_models.Question.options
                )
            )
            .order_by(attempt_models.AttemptQuestion.display_order)
        ).scalars().all()
    )
    aq_by_qid = {aq.question_id: aq for aq in aq_rows}

    items: list[AttemptQuestionReviewItem] = []
    for outcome in outcomes:
        aq = aq_by_qid.get(outcome.question_id)
        if aq is None:
            continue
        ordered_opts = _order_options_by_snapshot(aq.question.options, aq.option_order)
        review_options = [
            AttemptQuestionReviewOption(
                id=opt.id,
                label=VALID_OPTION_LABELS[idx],
                option_text=opt.option_text,
                is_correct=bool(opt.is_correct),
            )
            for idx, opt in enumerate(ordered_opts)
        ]
        items.append(
            AttemptQuestionReviewItem(
                question_id=outcome.question_id,
                display_order=aq.display_order,
                question_text=aq.question.question_text,
                selected_option_id=outcome.selected_option_id,
                correct_option_id=outcome.correct_option_id,
                is_correct=outcome.is_correct,
                points_earned=outcome.points_earned,
                points_available=outcome.points_available,
                options=review_options,
            )
        )
    return items


def _build_result_payload(
    db: Session,
    *,
    attempt: attempt_models.ExamAttempt,
    exam: exam_models.Exam,
    is_admin: bool = False,
    student: ApplicationUser | None = None,
) -> AttemptResultOut | AttemptSubmittedHiddenOut:
    started_at = ensure_utc(attempt.started_at)
    expires_at = ensure_utc(attempt.expires_at)
    submitted_at = (
        ensure_utc(attempt.submitted_at) if attempt.submitted_at is not None else None
    )

    if not is_admin and not can_view_student_result(attempt, exam):
        return AttemptSubmittedHiddenOut(
            attempt_id=attempt.id,
            exam_id=exam.id,
            exam_title=exam.title,
            status=attempt.status,
            submission_reason=attempt.submission_reason,
            started_at=started_at,
            expires_at=expires_at,
            submitted_at=submitted_at,
            total_questions=attempt.total_questions,
            message="Examination submitted. Results are withheld by the administrator.",
        )

    if is_admin and attempt.status != "GRADED":
        return AttemptResultOut(
            attempt_id=attempt.id,
            exam_id=exam.id,
            exam_title=exam.title,
            status=attempt.status,
            submission_reason=attempt.submission_reason,
            started_at=started_at,
            expires_at=expires_at,
            submitted_at=submitted_at,
            total_questions=attempt.total_questions,
            correct_answers=0,
            incorrect_answers=0,
            unanswered_questions=attempt.total_questions,
            points_earned=Decimal("0.00"),
            points_available=Decimal("0.00"),
            percentage=Decimal("0.00"),
            pass_mark=_quantize(exam.pass_mark),
            passed=False,
            show_correct_answers=bool(exam.show_correct_answers),
            question_review=None,
            student_user_id=student.id if student is not None else attempt.user_id,
            student_email=student.email if student is not None else None,
            student_display_name=student.display_name if student is not None else None,
        )

    persisted = project_persisted_result(attempt)
    review_items = _build_question_review_items(
        db,
        attempt=attempt,
        exam=exam,
        is_admin=is_admin,
    )
    disclosed_answer_key = True if is_admin else can_view_correct_answers(attempt, exam)
    return AttemptResultOut(
        attempt_id=persisted.attempt_id,
        exam_id=persisted.exam_id,
        exam_title=exam.title,
        status=persisted.status,
        submission_reason=persisted.submission_reason,
        started_at=persisted.started_at,
        expires_at=persisted.expires_at,
        submitted_at=persisted.submitted_at,
        total_questions=persisted.total_questions,
        correct_answers=persisted.correct_answers,
        incorrect_answers=persisted.incorrect_answers,
        unanswered_questions=persisted.unanswered_questions,
        points_earned=persisted.points_earned,
        points_available=persisted.points_available,
        percentage=persisted.percentage,
        pass_mark=_quantize(exam.pass_mark),
        passed=persisted.passed,
        show_correct_answers=disclosed_answer_key,
        question_review=review_items,
        student_user_id=student.id if is_admin and student is not None else None,
        student_email=student.email if is_admin and student is not None else None,
        student_display_name=student.display_name if is_admin and student is not None else None,
    )


def _to_start_response(
    attempt: attempt_models.ExamAttempt,
    *,
    duration_minutes: int,
    now: datetime,
    resumed: bool,
) -> AttemptStartResponse:
    return AttemptStartResponse(
        attempt_id=attempt.id,
        exam_id=attempt.exam_id,
        status=attempt.status,
        started_at=ensure_utc(attempt.started_at),
        expires_at=ensure_utc(attempt.expires_at),
        server_now=now,
        total_questions=attempt.total_questions,
        duration_minutes=duration_minutes,
        resumed=resumed,
    )


def start_attempt(
    db: Session,
    *,
    exam_id: UUID,
    student_user_id: UUID,
) -> AttemptStartResponse:
    """Start a new attempt or idempotently resume the active ``IN_PROGRESS`` sitting."""
    locked_user = db.execute(
        select(ApplicationUser.id)
        .where(ApplicationUser.id == student_user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if locked_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Application identity not established",
            headers={"WWW-Authenticate": "Bearer"},
        )

    exam = db.execute(
        select(exam_models.Exam)
        .where(exam_models.Exam.id == exam_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if exam is None or exam.status == "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination not found",
        )
    if exam.status != "PUBLISHED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Examination is closed and cannot accept new attempts",
        )

    now = utc_now()
    existing_attempts = list(
        db.execute(
            select(attempt_models.ExamAttempt)
            .where(
                attempt_models.ExamAttempt.exam_id == exam.id,
                attempt_models.ExamAttempt.user_id == student_user_id,
            )
            .order_by(attempt_models.ExamAttempt.started_at.desc())
        ).scalars().all()
    )

    for existing in existing_attempts:
        if existing.status != "IN_PROGRESS":
            continue
        if is_expired(existing.expires_at, now=now):
            _finalize_expired_attempt_in_tx(
                db,
                attempt_id=existing.id,
                exam=exam,
                now=now,
            )
        else:
            return _to_start_response(
                existing,
                duration_minutes=exam.duration_minutes,
                now=now,
                resumed=True,
            )

    if len(existing_attempts) >= exam.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum number of attempts reached for this examination",
        )

    all_questions = list(
        db.execute(
            select(exam_models.Question)
            .where(exam_models.Question.exam_id == exam.id)
            .options(selectinload(exam_models.Question.options))
            .order_by(exam_models.Question.position, exam_models.Question.id)
        ).scalars().all()
    )
    if not all_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Examination has no questions",
        )

    selected_questions = list(all_questions)
    if exam.randomize_questions:
        _SYSTEM_RANDOM.shuffle(selected_questions)
    if exam.question_limit is not None and exam.question_limit < len(selected_questions):
        selected_questions = selected_questions[: exam.question_limit]

    started_at = now
    expires_at = compute_expires_at(started_at, exam.duration_minutes)

    attempt = attempt_models.ExamAttempt(
        id=uuid4(),
        exam_id=exam.id,
        user_id=student_user_id,
        started_at=started_at,
        expires_at=expires_at,
        status="IN_PROGRESS",
        total_questions=len(selected_questions),
    )
    db.add(attempt)
    db.flush()

    for display_order, question in enumerate(selected_questions):
        ordered_opts = sorted(question.options, key=lambda o: (o.position, o.id))
        if exam.randomize_options and not question.source_file_id:
            _SYSTEM_RANDOM.shuffle(ordered_opts)
        aq = attempt_models.AttemptQuestion(
            attempt_id=attempt.id,
            question_id=question.id,
            display_order=display_order,
            option_order=_serialize_option_order(ordered_opts),
        )
        db.add(aq)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raced_active = db.execute(
            select(attempt_models.ExamAttempt).where(
                attempt_models.ExamAttempt.exam_id == exam.id,
                attempt_models.ExamAttempt.user_id == student_user_id,
                attempt_models.ExamAttempt.status == "IN_PROGRESS",
            )
        ).scalar_one_or_none()
        if raced_active is not None and not is_expired(raced_active.expires_at, now=utc_now()):
            return _to_start_response(
                raced_active,
                duration_minutes=exam.duration_minutes,
                now=utc_now(),
                resumed=True,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to start attempt due to concurrent request",
        ) from exc

    db.refresh(attempt)
    return _to_start_response(
        attempt,
        duration_minutes=exam.duration_minutes,
        now=now,
        resumed=False,
    )


def get_attempt_for_delivery(
    db: Session,
    *,
    attempt_id: UUID,
    student_user_id: UUID,
) -> AttemptDelivery:
    """Deliver active attempt questions, frozen option order, saved answers, and UTC deadline."""
    attempt = _load_attempt_for_student(
        db,
        attempt_id=attempt_id,
        student_user_id=student_user_id,
        for_update=False,
    )
    exam = _load_exam_or_404(db, attempt.exam_id)

    if attempt.status == "GRADED":
        raise AttemptConflictException(
            detail="Attempt has already been finalized.",
            code="ATTEMPT_ALREADY_GRADED",
            attempt_id=attempt.id,
            attempt_status="GRADED",
        )

    now = utc_now()
    if attempt.status == "IN_PROGRESS" and is_expired(attempt.expires_at, now=now):
        finalized = _finalize_expired_attempt_in_tx(
            db,
            attempt_id=attempt.id,
            exam=exam,
            now=now,
        )
        raise AttemptConflictException(
            detail="Examination time has expired. Your attempt has been finalized.",
            code="ATTEMPT_EXPIRED",
            attempt_id=finalized.id,
            attempt_status=finalized.status,
        )

    if attempt.status != "IN_PROGRESS":
        raise AttemptConflictException(
            detail="Attempt has already been finalized.",
            code="ATTEMPT_ALREADY_GRADED",
            attempt_id=attempt.id,
            attempt_status=attempt.status,
        )

    aq_rows = list(
        db.execute(
            select(attempt_models.AttemptQuestion)
            .where(attempt_models.AttemptQuestion.attempt_id == attempt.id)
            .options(
                selectinload(attempt_models.AttemptQuestion.question).selectinload(
                    exam_models.Question.options
                )
            )
            .order_by(attempt_models.AttemptQuestion.display_order)
        ).scalars().all()
    )

    answer_rows = list(
        db.execute(
            select(attempt_models.StudentAnswer).where(
                attempt_models.StudentAnswer.attempt_id == attempt.id
            )
        ).scalars().all()
    )
    saved_answers: dict[UUID, UUID | None] = {
        ans.question_id: ans.selected_option_id for ans in answer_rows
    }

    question_deliveries: list[AttemptQuestionDelivery] = []
    for aq in aq_rows:
        question = aq.question
        ordered_opts = (
            sorted(question.options, key=lambda opt: opt.position)
            if question.source_file_id else
            _order_options_by_snapshot(question.options, aq.option_order)
        )
        option_deliveries = [
            AttemptOptionDelivery(
                id=opt.id,
                label=VALID_OPTION_LABELS[idx],
                option_text=opt.option_text,
            )
            for idx, opt in enumerate(ordered_opts)
        ]
        question_deliveries.append(
            AttemptQuestionDelivery(
                id=question.id,
                display_order=aq.display_order,
                question_text=question.question_text,
                image_urls=(
                    [f"/api/attempts/{attempt.id}/questions/{question.id}/images/{i}"
                     for i, _ in enumerate(json.loads(question.image_regions or "[]"))]
                    if question.source_file_id else []
                ),
                points=_quantize(question.points),
                options=option_deliveries,
            )
        )

    return AttemptDelivery(
        attempt_id=attempt.id,
        exam_id=exam.id,
        exam_title=exam.title,
        duration_minutes=exam.duration_minutes,
        status=attempt.status,
        started_at=ensure_utc(attempt.started_at),
        expires_at=ensure_utc(attempt.expires_at),
        server_now=now,
        total_questions=attempt.total_questions,
        questions=question_deliveries,
        saved_answers=saved_answers,
    )


def save_answer(
    db: Session,
    *,
    attempt_id: UUID,
    question_id: UUID,
    selected_option_id: UUID | None,
    student_user_id: UUID,
) -> AnswerSaveResponse:
    """Validate attempt/timer/question/option and atomically upsert student answer."""
    attempt = _load_attempt_for_student(
        db,
        attempt_id=attempt_id,
        student_user_id=student_user_id,
        for_update=True,
    )
    exam = _load_exam_or_404(db, attempt.exam_id)

    if attempt.status != "IN_PROGRESS":
        raise AttemptConflictException(
            detail="Attempt has already been finalized; answers are locked.",
            code="ATTEMPT_ALREADY_GRADED",
            attempt_id=attempt.id,
            attempt_status=attempt.status,
        )

    now = utc_now()
    if is_expired(attempt.expires_at, now=now):
        finalize_attempt_locked(
            db,
            attempt,
            exam,
            reason="TIMER_EXPIRED",
            now=now,
        )
        db.commit()
        raise AttemptConflictException(
            detail="Examination time has expired. Your attempt has been finalized.",
            code="ATTEMPT_EXPIRED",
            attempt_id=attempt.id,
            attempt_status="GRADED",
        )

    aq = db.execute(
        select(attempt_models.AttemptQuestion).where(
            attempt_models.AttemptQuestion.attempt_id == attempt.id,
            attempt_models.AttemptQuestion.question_id == question_id,
        )
    ).scalar_one_or_none()
    if aq is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question does not belong to this attempt",
        )

    if selected_option_id is not None:
        option = db.execute(
            select(exam_models.QuestionOption).where(
                exam_models.QuestionOption.id == selected_option_id,
                exam_models.QuestionOption.question_id == question_id,
            )
        ).scalar_one_or_none()
        if option is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected option does not belong to this question",
            )

    table = cast(Table, attempt_models.StudentAnswer.__table__)
    bind = db.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""

    if dialect_name in {"postgresql", "sqlite"}:
        insert_fn = pg_insert if dialect_name == "postgresql" else sqlite_insert
        stmt = insert_fn(table).values(
            id=uuid4(),
            attempt_id=attempt.id,
            question_id=question_id,
            selected_option_id=selected_option_id,
            answered_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.attempt_id, table.c.question_id],
            set_={
                "selected_option_id": selected_option_id,
                "updated_at": now,
            },
        ).returning(
            table.c.answered_at,
            table.c.updated_at,
            table.c.selected_option_id,
        )
        row = db.execute(stmt).one()
        answered_at = ensure_utc(row.answered_at)
        updated_at = ensure_utc(row.updated_at)
        persisted_option_id = row.selected_option_id
    else:
        existing = db.execute(
            select(attempt_models.StudentAnswer).where(
                attempt_models.StudentAnswer.attempt_id == attempt.id,
                attempt_models.StudentAnswer.question_id == question_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            created = attempt_models.StudentAnswer(
                id=uuid4(),
                attempt_id=attempt.id,
                question_id=question_id,
                selected_option_id=selected_option_id,
                answered_at=now,
                updated_at=now,
            )
            db.add(created)
            answered_at = now
            updated_at = now
            persisted_option_id = selected_option_id
        else:
            existing.selected_option_id = selected_option_id
            existing.updated_at = now
            db.add(existing)
            answered_at = ensure_utc(existing.answered_at)
            updated_at = now
            persisted_option_id = selected_option_id

    db.commit()
    return AnswerSaveResponse(
        attempt_id=attempt.id,
        question_id=question_id,
        selected_option_id=persisted_option_id,
        answered_at=answered_at,
        updated_at=updated_at,
    )


def submit_attempt(
    db: Session,
    *,
    attempt_id: UUID,
    student_user_id: UUID,
    confirm: bool = True,
) -> AttemptResultOut | AttemptSubmittedHiddenOut:
    """Idempotently finalize and grade an attempt under row lock."""
    attempt = _load_attempt_for_student(
        db,
        attempt_id=attempt_id,
        student_user_id=student_user_id,
        for_update=True,
    )
    exam = _load_exam_or_404(db, attempt.exam_id)

    if attempt.status == "GRADED":
        return _build_result_payload(db, attempt=attempt, exam=exam, is_admin=False)

    now = utc_now()
    reason: SubmissionReason = resolve_submission_reason(
        attempt.expires_at,
        requested_reason="STUDENT_SUBMITTED",
        now=now,
    )
    if reason == "STUDENT_SUBMITTED" and not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission requires confirmation",
        )

    finalize_attempt_locked(db, attempt, exam, reason=reason, now=now)
    db.commit()
    db.refresh(attempt)
    return _build_result_payload(db, attempt=attempt, exam=exam, is_admin=False)


def finalize_expired_attempt(
    db: Session,
    *,
    attempt_id: UUID,
    student_user_id: UUID,
) -> AttemptResultOut | AttemptSubmittedHiddenOut | None:
    """Finalize an expired attempt via the shared grading/finalization engine."""
    attempt = _load_attempt_for_student(
        db,
        attempt_id=attempt_id,
        student_user_id=student_user_id,
        for_update=True,
    )
    exam = _load_exam_or_404(db, attempt.exam_id)

    if attempt.status == "GRADED":
        return _build_result_payload(db, attempt=attempt, exam=exam, is_admin=False)

    now = utc_now()
    if not is_expired(attempt.expires_at, now=now):
        return None

    finalize_attempt_locked(db, attempt, exam, reason="TIMER_EXPIRED", now=now)
    db.commit()
    db.refresh(attempt)
    return _build_result_payload(db, attempt=attempt, exam=exam, is_admin=False)


def get_attempt_result(
    db: Session,
    *,
    attempt_id: UUID,
    student_user_id: UUID,
) -> AttemptResultOut | AttemptSubmittedHiddenOut:
    """Return a student's finalized attempt result respecting disclosure rules."""
    attempt = _load_attempt_for_student(
        db,
        attempt_id=attempt_id,
        student_user_id=student_user_id,
        for_update=False,
    )
    exam = _load_exam_or_404(db, attempt.exam_id)

    now = utc_now()
    if attempt.status == "IN_PROGRESS":
        if is_expired(attempt.expires_at, now=now):
            attempt = _finalize_expired_attempt_in_tx(
                db,
                attempt_id=attempt.id,
                exam=exam,
                now=now,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Attempt is still in progress; submit before viewing results",
            )

    if attempt.status != "GRADED":
        attempt = _finalize_expired_attempt_in_tx(
            db,
            attempt_id=attempt.id,
            exam=exam,
            now=now,
        )

    return _build_result_payload(db, attempt=attempt, exam=exam, is_admin=False)


def list_student_attempts(
    db: Session,
    *,
    student_user_id: UUID,
) -> list[StudentAttemptSummary]:
    """List the caller's attempts across exams, hiding gated or active scores."""
    rows = list(
        db.execute(
            select(attempt_models.ExamAttempt, exam_models.Exam)
            .join(exam_models.Exam, attempt_models.ExamAttempt.exam_id == exam_models.Exam.id)
            .where(attempt_models.ExamAttempt.user_id == student_user_id)
            .order_by(attempt_models.ExamAttempt.started_at.desc())
        ).all()
    )
    if not rows:
        return []

    now = utc_now()
    summaries: list[StudentAttemptSummary] = []
    for attempt, exam in rows:
        if attempt.status == "IN_PROGRESS" and is_expired(attempt.expires_at, now=now):
            attempt = _finalize_expired_attempt_in_tx(
                db,
                attempt_id=attempt.id,
                exam=exam,
                now=now,
            )

        visible = can_view_student_result(attempt, exam)
        summaries.append(
            StudentAttemptSummary(
                attempt_id=attempt.id,
                exam_id=exam.id,
                exam_title=exam.title,
                status=attempt.status,
                submission_reason=attempt.submission_reason,
                started_at=ensure_utc(attempt.started_at),
                expires_at=ensure_utc(attempt.expires_at),
                submitted_at=(
                    ensure_utc(attempt.submitted_at)
                    if attempt.submitted_at is not None
                    else None
                ),
                total_questions=attempt.total_questions,
                result_visible=visible,
                points_earned=_quantize(attempt.points_earned) if visible else None,
                points_available=_quantize(attempt.points_available) if visible else None,
                percentage=_quantize(attempt.percentage) if visible else None,
                passed=bool(attempt.passed) if visible else None,
            )
        )
    return summaries


def get_admin_exam_results(
    db: Session,
    *,
    exam_id: UUID,
    admin_user_id: UUID,
) -> ExamAdminResultsResponse:
    """Return full administrator results table and aggregate metrics for an exam."""
    _ = admin_user_id
    exam = _load_exam_or_404(db, exam_id)

    rows = list(
        db.execute(
            select(attempt_models.ExamAttempt, ApplicationUser)
            .join(
                ApplicationUser,
                attempt_models.ExamAttempt.user_id == ApplicationUser.id,
            )
            .where(attempt_models.ExamAttempt.exam_id == exam.id)
            .order_by(
                attempt_models.ExamAttempt.submitted_at.desc().nullslast(),
                attempt_models.ExamAttempt.started_at.desc(),
            )
        ).all()
    )

    now = utc_now()
    resolved_rows: list[tuple[attempt_models.ExamAttempt, ApplicationUser]] = []
    for attempt, student in rows:
        if attempt.status == "IN_PROGRESS" and is_expired(attempt.expires_at, now=now):
            attempt = _finalize_expired_attempt_in_tx(
                db,
                attempt_id=attempt.id,
                exam=exam,
                now=now,
            )
        resolved_rows.append((attempt, student))

    attempts_only = [attempt for attempt, _student in resolved_rows]
    summary_dict = compute_exam_results_summary(attempts_only)
    summary = ExamResultsSummary.model_validate(summary_dict)

    attempt_rows = [
        ExamAdminAttemptRow(
            attempt_id=attempt.id,
            user_id=student.id,
            email=student.email,
            display_name=student.display_name,
            status=attempt.status,
            submission_reason=attempt.submission_reason,
            started_at=ensure_utc(attempt.started_at),
            expires_at=ensure_utc(attempt.expires_at),
            submitted_at=(
                ensure_utc(attempt.submitted_at)
                if attempt.submitted_at is not None
                else None
            ),
            total_questions=attempt.total_questions,
            correct_answers=attempt.correct_answers,
            incorrect_answers=attempt.incorrect_answers,
            unanswered_questions=attempt.unanswered_questions,
            points_earned=_quantize(attempt.points_earned),
            points_available=_quantize(attempt.points_available),
            percentage=_quantize(attempt.percentage),
            passed=bool(attempt.passed),
        )
        for attempt, student in resolved_rows
    ]

    return ExamAdminResultsResponse(
        exam_id=exam.id,
        exam_title=exam.title,
        pass_mark=_quantize(exam.pass_mark),
        total_attempts=len(attempt_rows),
        summary=summary,
        attempts=attempt_rows,
    )


def get_admin_attempt_detail(
    db: Session,
    *,
    attempt_id: UUID,
    admin_user_id: UUID,
) -> AttemptResultOut:
    """Return full administrator inspection details for a single attempt."""
    _ = admin_user_id
    attempt = db.get(attempt_models.ExamAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found",
        )
    exam = _load_exam_or_404(db, attempt.exam_id)
    student = db.get(ApplicationUser, attempt.user_id)

    now = utc_now()
    if attempt.status == "IN_PROGRESS" and is_expired(attempt.expires_at, now=now):
        attempt = _finalize_expired_attempt_in_tx(
            db,
            attempt_id=attempt.id,
            exam=exam,
            now=now,
        )

    result = _build_result_payload(
        db,
        attempt=attempt,
        exam=exam,
        is_admin=True,
        student=student,
    )
    if not isinstance(result, AttemptResultOut):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to construct admin attempt detail",
        )
    return result
