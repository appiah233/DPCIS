"""Examination domain service layer (Literate Engineering spec).

Problem
-------
Provide a strictly role-isolated, transactional examination authoring and
lifecycle service supporting ``DRAFT -> PUBLISHED -> CLOSED`` transitions,
bulk and single-question MCQ CRUD, preview parsing, publication validation,
and student-safe examination discovery.

Invariants
----------
1. **Role & Identity Authority:** Admin operations verify ``ROLE_ADMIN`` and
   require a resolved ``identity.user_id`` UUID from ``application_users``
   (never raw ``identity.subject``). Student read operations verify
   ``ROLE_STUDENT`` and ``identity.user_id``.
2. **Lifecycle State Machine:** New exams start in ``DRAFT`` with
   ``published_at=None`` and ``closed_at=None``. Only ``publish_exam`` may
   transition ``DRAFT -> PUBLISHED`` (stamping ``published_at``), and only
   ``close_exam`` may transition ``PUBLISHED -> CLOSED`` (stamping
   ``closed_at``). Direct status edits via ``update_exam`` are forbidden.
3. **Historical Score Protection:** Any exam in ``PUBLISHED`` or ``CLOSED``
   state is immutable for settings, question edits/additions/deletions, and
   exam deletion (``409 Conflict``), guaranteeing historical attempts and
   scores cannot be invalidated retroactively.
4. **Answer-Key Isolation:** Student queries project exam metadata,
   ``COUNT(questions.id)``, and the student's own ``exam_attempts`` summary
   without ever querying ``question_options`` or exposing ``is_correct``.
   Non-``PUBLISHED`` exams return ``404`` to students to prevent enumeration.
5. **Transactional Concurrency Serialization:** Read-then-mutate exam
   operations (``update_exam``, ``delete_exam``, ``save_questions``,
   ``add_question``, ``update_question``, ``delete_question``,
   ``publish_exam``, ``close_exam``) acquire a row-level ``FOR UPDATE`` lock
   on the parent ``exams`` row via ``_get_exam_or_404(..., for_update=True)``
   before reading state or computing derived question positions under
   PostgreSQL ``READ COMMITTED``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.attempts import models as attempt_models
from app.auth.dependencies import ROLE_ADMIN, ROLE_STUDENT, AuthIdentity
from app.exams import models as exam_models
from app.exams.parser import parse_questions_with_answer_key
from app.exams.schemas import (
    VALID_OPTION_LABELS,
    ExamAdminOut,
    ExamCreate,
    ExamStatus,
    ExamStudentOut,
    ExamUpdate,
    ExamWithQuestionsAdmin,
    ParseQuestionsResponse,
    QuestionAdminOut,
    QuestionCreate,
    QuestionOptionAdminOut,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


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


def _get_exam_or_404(
    db: Session,
    exam_id: UUID,
    *,
    load_questions: bool = False,
    for_update: bool = False,
) -> exam_models.Exam:
    if load_questions or for_update:
        stmt = select(exam_models.Exam).where(exam_models.Exam.id == exam_id)
        if load_questions:
            stmt = stmt.options(
                selectinload(exam_models.Exam.questions).selectinload(
                    exam_models.Question.options
                )
            )
        if for_update:
            stmt = stmt.with_for_update()
        stmt = stmt.execution_options(populate_existing=True)
        exam = db.execute(stmt).scalar_one_or_none()
    else:
        exam = db.get(exam_models.Exam, exam_id)

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination not found",
        )
    return exam


def _require_draft(exam: exam_models.Exam, detail: str) -> None:
    if exam.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


def _count_exam_questions(db: Session, exam_id: UUID) -> int:
    count_val = db.execute(
        select(func.count(exam_models.Question.id)).where(
            exam_models.Question.exam_id == exam_id
        )
    ).scalar_one()
    return int(count_val or 0)


def _to_question_admin_out(question: exam_models.Question) -> QuestionAdminOut:
    sorted_options = sorted(question.options, key=lambda o: (o.position, o.label))
    return QuestionAdminOut(
        id=question.id,
        question_text=question.question_text,
        source_file_id=question.source_file_id,
        source_number=question.source_number,
        image_urls=(
            [f"/api/admin/exams/{question.exam_id}/source-images/{question.source_file_id}/{question.source_number}/{i}"
             for i, _ in enumerate(json.loads(question.image_regions or "[]"))]
            if question.source_file_id else []
        ),
        image_regions=json.loads(question.image_regions or "[]"),
        pdf_options_text=json.loads(question.pdf_options_text or "{}"),
        pdf_warnings=json.loads(question.pdf_warnings or "[]"),
        pdf_confidence=question.pdf_confidence,
        position=question.position,
        points=question.points,
        options=[QuestionOptionAdminOut.model_validate(opt) for opt in sorted_options],
    )


def _to_exam_admin_out(exam: exam_models.Exam, *, question_count: int) -> ExamAdminOut:
    return ExamAdminOut(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        instructions=exam.instructions,
        duration_minutes=exam.duration_minutes,
        pass_mark=exam.pass_mark,
        question_limit=exam.question_limit,
        randomize_questions=exam.randomize_questions,
        randomize_options=exam.randomize_options,
        max_attempts=exam.max_attempts,
        show_result=exam.show_result,
        show_correct_answers=exam.show_correct_answers,
        status=exam.status,
        created_by=exam.created_by,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        published_at=exam.published_at,
        closed_at=exam.closed_at,
        question_count=question_count,
    )


def _to_exam_with_questions_admin(exam: exam_models.Exam) -> ExamWithQuestionsAdmin:
    sorted_questions = sorted(
        exam.questions,
        key=lambda q: (q.position, q.created_at, str(q.id)),
    )
    question_outs = [_to_question_admin_out(q) for q in sorted_questions]
    base = _to_exam_admin_out(exam, question_count=len(question_outs))
    return ExamWithQuestionsAdmin(
        **base.model_dump(),
        questions=question_outs,
    )


def _build_question_model(
    *,
    exam_id: UUID,
    data: QuestionCreate,
    position: int,
) -> exam_models.Question:
    question_id = uuid4()
    options = [
        exam_models.QuestionOption(
            id=uuid4(),
            question_id=question_id,
            label=opt.label,
            option_text=opt.option_text,
            is_correct=opt.is_correct,
            position=pos,
        )
        for pos, opt in enumerate(data.options)
    ]
    return exam_models.Question(
        id=question_id,
        exam_id=exam_id,
        question_text=data.question_text,
        source_file_id=data.source_file_id,
        source_number=data.source_number,
        pdf_options_text=json.dumps(data.pdf_options_text) if data.source_file_id else None,
        pdf_warnings=json.dumps(data.pdf_warnings) if data.source_file_id else None,
        pdf_confidence=data.pdf_confidence if data.source_file_id else None,
        position=position,
        points=data.points,
        options=options,
    )


def _validate_source_reference(db: Session, exam_id: UUID, data: QuestionCreate) -> str | None:
    if data.source_file_id is None:
        if data.source_number is not None:
            raise HTTPException(status_code=400, detail="PDF question number needs a source file")
        return None
    source = db.get(exam_models.ExamSourceFile, data.source_file_id)
    if source is None or source.exam_id != exam_id or data.source_number is None:
        raise HTTPException(status_code=400, detail="Invalid PDF source for question")
    from app.exams.pdf_storage import load_regions

    try:
        return json.dumps(load_regions(data.source_file_id, data.source_number))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="PDF question crop is unavailable") from exc


def _image_paths_json(source_number: int | None, image_regions: str | None) -> str | None:
    if source_number is None or image_regions is None:
        return None
    return json.dumps(
        [f"{source_number}-{index}.png" for index, _ in enumerate(json.loads(image_regions))]
    )


def _resolve_bulk_positions(questions: list[QuestionCreate]) -> list[int]:
    if not questions:
        return []
    explicit = [q.position for q in questions]
    if all(pos is not None for pos in explicit):
        resolved = [int(pos) for pos in explicit if pos is not None]
        if len(set(resolved)) != len(resolved):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Question positions must be unique",
            )
        return resolved

    # Validate any partially provided positions are unique, then normalize sequentially.
    provided = [pos for pos in explicit if pos is not None]
    if len(set(provided)) != len(provided):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Question positions must be unique",
        )
    return list(range(len(questions)))


# ---------------------------------------------------------------------------
# Admin exam authoring & lifecycle
# ---------------------------------------------------------------------------


def create_exam(
    db: Session,
    identity: AuthIdentity,
    data: ExamCreate,
) -> ExamAdminOut:
    """Create a new examination in DRAFT state owned by ``identity.user_id``."""
    admin_user_id = require_admin_user_id(identity)
    now = _utc_now()

    exam = exam_models.Exam(
        id=uuid4(),
        title=data.title,
        description=data.description,
        instructions=data.instructions,
        duration_minutes=data.duration_minutes,
        pass_mark=data.pass_mark,
        question_limit=data.question_limit,
        randomize_questions=data.randomize_questions,
        randomize_options=data.randomize_options,
        max_attempts=data.max_attempts,
        show_result=data.show_result,
        show_correct_answers=data.show_correct_answers,
        status="DRAFT",
        created_by=admin_user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _to_exam_admin_out(exam, question_count=0)


def list_exams_admin(
    db: Session,
    identity: AuthIdentity,
    status_filter: ExamStatus | None = None,
) -> list[ExamAdminOut]:
    """List all examinations with question counts for an ADMIN caller."""
    require_admin_user_id(identity)

    stmt = (
        select(
            exam_models.Exam,
            func.count(exam_models.Question.id).label("question_count"),
        )
        .outerjoin(
            exam_models.Question,
            exam_models.Question.exam_id == exam_models.Exam.id,
        )
        .group_by(exam_models.Exam.id)
        .order_by(exam_models.Exam.created_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(exam_models.Exam.status == status_filter)

    rows = db.execute(stmt).all()
    return [
        _to_exam_admin_out(exam, question_count=int(q_count or 0))
        for exam, q_count in rows
    ]


def get_exam_admin(
    db: Session,
    exam_id: UUID,
    identity: AuthIdentity,
) -> ExamWithQuestionsAdmin:
    """Fetch full examination details including questions and answer keys."""
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, load_questions=True)
    return _to_exam_with_questions_admin(exam)


def update_exam(
    db: Session,
    exam_id: UUID,
    identity: AuthIdentity,
    data: ExamUpdate,
) -> ExamAdminOut:
    """Update a DRAFT examination. Any authenticated ADMIN may modify drafts."""
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, for_update=True)
    _require_draft(exam, "Only draft examinations can be modified")

    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("status", None)
    for field, value in update_data.items():
        setattr(exam, field, value)
    exam.updated_at = _utc_now()

    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _to_exam_admin_out(
        exam,
        question_count=_count_exam_questions(db, exam.id),
    )


def delete_exam(
    db: Session,
    exam_id: UUID,
    identity: AuthIdentity,
) -> None:
    """Delete a DRAFT examination. Published/closed exams cannot be deleted."""
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, for_update=True)
    _require_draft(exam, "Only draft examinations can be deleted")

    attempt_count = db.execute(
        select(func.count(attempt_models.ExamAttempt.id)).where(
            attempt_models.ExamAttempt.exam_id == exam.id
        )
    ).scalar_one()
    if int(attempt_count or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Examinations with recorded attempts cannot be deleted",
        )

    db.delete(exam)
    db.commit()


def save_questions(
    db: Session,
    exam_id: UUID,
    identity: AuthIdentity,
    questions: list[QuestionCreate],
) -> ExamWithQuestionsAdmin:
    """Transactionally replace all questions on a DRAFT examination."""
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, load_questions=True, for_update=True)
    _require_draft(exam, "Questions can only be saved on a draft examination")

    # A repeated import may refer to the same PDF through different source IDs.
    # Keep its last editor entry for each source question; different PDFs remain additive.
    unique: list[tuple[QuestionCreate, str | None]] = []
    pdf_positions: dict[tuple[str, int], int] = {}
    for item in questions:
        image_regions = _validate_source_reference(db, exam.id, item)
        if item.source_file_id is not None and item.source_number is not None:
            source = db.get(exam_models.ExamSourceFile, item.source_file_id)
            if source is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Question PDF source is unavailable",
                )
            key = (source.sha256, item.source_number)
            prior = pdf_positions.get(key)
            if prior is not None:
                unique[prior] = (item, image_regions)
                continue
            pdf_positions[key] = len(unique)
        unique.append((item, image_regions))

    deduplicated = [item for item, _ in unique]
    positions = (
        list(range(len(unique))) if len(unique) != len(questions)
        else _resolve_bulk_positions(deduplicated)
    )

    exam.questions.clear()
    db.flush()

    for (q_data, image_regions), pos in zip(unique, positions, strict=True):
        question = _build_question_model(
            exam_id=exam.id,
            data=q_data,
            position=pos,
        )
        question.image_regions = image_regions
        question.image_paths = _image_paths_json(q_data.source_number, image_regions)
        exam.questions.append(question)

    exam.updated_at = _utc_now()
    db.add(exam)
    db.commit()

    refreshed = _get_exam_or_404(db, exam.id, load_questions=True)
    return _to_exam_with_questions_admin(refreshed)


def add_question(
    db: Session,
    exam_id: UUID,
    identity: AuthIdentity,
    data: QuestionCreate,
) -> QuestionAdminOut:
    """Append or insert a single question into a DRAFT examination."""
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, for_update=True)
    _require_draft(exam, "Questions can only be added to a draft examination")
    image_regions = _validate_source_reference(db, exam.id, data)

    existing_positions = set(
        db.execute(
            select(exam_models.Question.position).where(
                exam_models.Question.exam_id == exam.id
            )
        ).scalars().all()
    )

    if data.position is None:
        position = (max(existing_positions) + 1) if existing_positions else 0
    elif data.position in existing_positions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Question position {data.position} already exists",
        )
    else:
        position = data.position

    question = _build_question_model(
        exam_id=exam.id,
        data=data,
        position=position,
    )
    question.image_regions = image_regions
    question.image_paths = _image_paths_json(data.source_number, image_regions)
    exam.updated_at = _utc_now()
    db.add(question)
    db.add(exam)
    db.commit()

    saved = db.execute(
        select(exam_models.Question)
        .where(exam_models.Question.id == question.id)
        .options(selectinload(exam_models.Question.options))
        .execution_options(populate_existing=True)
    ).scalar_one()
    return _to_question_admin_out(saved)


def update_question(
    db: Session,
    exam_id: UUID,
    question_id: UUID,
    identity: AuthIdentity,
    data: QuestionCreate,
) -> QuestionAdminOut:
    """Update a single question and its options on a DRAFT examination."""
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, for_update=True)
    _require_draft(exam, "Questions can only be modified on a draft examination")
    image_regions = _validate_source_reference(db, exam.id, data)

    question = db.execute(
        select(exam_models.Question)
        .where(
            exam_models.Question.id == question_id,
            exam_models.Question.exam_id == exam.id,
        )
        .options(selectinload(exam_models.Question.options))
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if data.position is not None and data.position != question.position:
        conflict = db.execute(
            select(exam_models.Question.id).where(
                exam_models.Question.exam_id == exam.id,
                exam_models.Question.id != question.id,
                exam_models.Question.position == data.position,
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Question position {data.position} already exists",
            )
        question.position = data.position

    now = _utc_now()
    question.question_text = data.question_text
    question.source_file_id = data.source_file_id
    question.source_number = data.source_number
    question.image_regions = image_regions
    question.image_paths = _image_paths_json(data.source_number, image_regions)
    question.pdf_options_text = json.dumps(data.pdf_options_text) if data.source_file_id else None
    question.pdf_warnings = json.dumps(data.pdf_warnings) if data.source_file_id else None
    question.pdf_confidence = data.pdf_confidence if data.source_file_id else None
    question.points = data.points
    question.updated_at = now

    question.options.clear()
    db.flush()

    for pos, opt in enumerate(data.options):
        question.options.append(
            exam_models.QuestionOption(
                id=uuid4(),
                question_id=question.id,
                label=opt.label,
                option_text=opt.option_text,
                is_correct=opt.is_correct,
                position=pos,
            )
        )

    exam.updated_at = now
    db.add(question)
    db.add(exam)
    db.commit()

    refreshed = db.execute(
        select(exam_models.Question)
        .where(exam_models.Question.id == question.id)
        .options(selectinload(exam_models.Question.options))
        .execution_options(populate_existing=True)
    ).scalar_one()
    return _to_question_admin_out(refreshed)


def delete_question(
    db: Session,
    exam_id: UUID,
    question_id: UUID,
    identity: AuthIdentity,
) -> None:
    """Delete a single question on a DRAFT exam and re-sequence remaining positions."""
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, for_update=True)
    _require_draft(exam, "Questions can only be deleted on a draft examination")

    question = db.execute(
        select(exam_models.Question).where(
            exam_models.Question.id == question_id,
            exam_models.Question.exam_id == exam.id,
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    db.delete(question)
    db.flush()

    remaining = list(
        db.execute(
            select(exam_models.Question)
            .where(exam_models.Question.exam_id == exam.id)
            .order_by(
                exam_models.Question.position,
                exam_models.Question.created_at,
                exam_models.Question.id,
            )
        ).scalars().all()
    )
    for new_pos, q in enumerate(remaining):
        q.position = new_pos
        db.add(q)

    exam.updated_at = _utc_now()
    db.add(exam)
    db.commit()


def publish_exam(
    db: Session,
    exam_id: UUID,
    identity: AuthIdentity,
) -> ExamAdminOut:
    """Publish a DRAFT examination after verifying all integrity invariants."""
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, for_update=True)
    _require_draft(exam, "Only draft examinations can be published")

    errors: list[str] = []

    if not exam.title or not exam.title.strip():
        errors.append("title is required")
    if not exam.duration_minutes or exam.duration_minutes <= 0:
        errors.append("duration_minutes must be greater than 0")
    if (
        exam.pass_mark is None
        or not Decimal(exam.pass_mark).is_finite()
        or exam.pass_mark < 0
        or exam.pass_mark > 100
    ):
        errors.append("pass_mark must be between 0 and 100")
    if not exam.max_attempts or exam.max_attempts < 1:
        errors.append("max_attempts must be at least 1")
    if exam.question_limit is not None and exam.question_limit < 1:
        errors.append("question_limit must be greater than 0")
    if not exam.show_result and exam.show_correct_answers:
        errors.append("show_correct_answers cannot be enabled when show_result is disabled")

    questions = list(
        db.execute(
            select(exam_models.Question)
            .where(exam_models.Question.exam_id == exam.id)
            .options(selectinload(exam_models.Question.options))
            .order_by(exam_models.Question.position)
        ).scalars().all()
    )

    if not questions:
        errors.append("at least one question is required")

    for idx, q in enumerate(questions, start=1):
        if not q.question_text or not q.question_text.strip():
            errors.append(f"question {idx} has empty text")
        if q.points is None or q.points <= 0:
            errors.append(f"question {idx} points must be greater than 0")

        opts = sorted(q.options, key=lambda o: (o.position, o.label))
        if len(opts) < 2 or len(opts) > 4:
            errors.append(f"question {idx} must have between 2 and 4 options")
        else:
            labels = [o.label for o in opts]
            expected_labels = list(VALID_OPTION_LABELS[: len(opts)])
            if len(set(labels)) != len(labels) or labels != expected_labels:
                errors.append(
                    f"question {idx} options must use unique sequential labels starting from A"
                )

            seen_texts: set[str] = set()
            for opt in opts:
                if not opt.option_text or not opt.option_text.strip():
                    errors.append(f"question {idx} option '{opt.label}' has empty text")
                    continue
                folded = " ".join(opt.option_text.split()).casefold()
                if folded in seen_texts:
                    errors.append(f"question {idx} contains duplicate option text")
                else:
                    seen_texts.add(folded)

        correct_opts = [o for o in opts if o.is_correct]
        if len(correct_opts) != 1:
            errors.append(f"question {idx} must have exactly one correct answer")

    if exam.question_limit is not None and exam.question_limit > len(questions):
        errors.append("question_limit exceeds the number of available questions")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "exam failed validation", "errors": errors},
        )

    now = _utc_now()
    exam.status = "PUBLISHED"
    exam.published_at = now
    exam.updated_at = now
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _to_exam_admin_out(exam, question_count=len(questions))


def close_exam(
    db: Session,
    exam_id: UUID,
    identity: AuthIdentity,
) -> ExamAdminOut:
    """Close a PUBLISHED examination (PUBLISHED -> CLOSED), stamping closed_at.

    Idempotent when already CLOSED (preserves the original ``closed_at``).
    Closing a DRAFT exam is rejected with ``409 Conflict``.
    """
    require_admin_user_id(identity)
    exam = _get_exam_or_404(db, exam_id, for_update=True)

    if exam.status == "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only published examinations can be closed",
        )

    if exam.status == "PUBLISHED":
        now = _utc_now()
        exam.status = "CLOSED"
        exam.closed_at = now
        exam.updated_at = now
        db.add(exam)
        db.commit()
        db.refresh(exam)

    return _to_exam_admin_out(
        exam,
        question_count=_count_exam_questions(db, exam.id),
    )


def parse_questions_service(
    raw_text: str, answer_key_text: str | None = None
) -> ParseQuestionsResponse:
    """Parse pasted question text without persisting (preview only)."""
    return parse_questions_with_answer_key(raw_text, answer_key_text)


# ---------------------------------------------------------------------------
# Student exam discovery (strictly PUBLISHED, zero answer-key projection)
# ---------------------------------------------------------------------------


def _build_student_exam_out(
    exam: exam_models.Exam,
    *,
    total_questions: int,
    attempts: list[attempt_models.ExamAttempt],
    now: datetime,
) -> ExamStudentOut:
    effective_question_count = (
        min(total_questions, exam.question_limit)
        if exam.question_limit is not None
        else total_questions
    )
    attempts_used = len(attempts)
    active_attempt_id = next(
        (
            a.id
            for a in attempts
            if a.status == "IN_PROGRESS" and _ensure_utc(a.expires_at) > now
        ),
        None,
    )
    can_start = bool(active_attempt_id is not None or attempts_used < exam.max_attempts)
    return ExamStudentOut(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        instructions=exam.instructions,
        duration_minutes=exam.duration_minutes,
        pass_mark=exam.pass_mark,
        question_limit=exam.question_limit,
        randomize_questions=exam.randomize_questions,
        randomize_options=exam.randomize_options,
        max_attempts=exam.max_attempts,
        show_result=exam.show_result,
        question_count=effective_question_count,
        attempts_used=attempts_used,
        active_attempt_id=active_attempt_id,
        can_start=can_start,
        published_at=exam.published_at,
    )


def list_available_exams(
    db: Session,
    student_user_id: UUID,
) -> list[ExamStudentOut]:
    """List PUBLISHED exams visible to a student without querying question options."""
    exams = list(
        db.execute(
            select(exam_models.Exam)
            .where(exam_models.Exam.status == "PUBLISHED")
            .order_by(exam_models.Exam.published_at.desc(), exam_models.Exam.created_at.desc())
        ).scalars().all()
    )
    if not exams:
        return []

    exam_ids = [exam.id for exam in exams]

    count_rows = db.execute(
        select(
            exam_models.Question.exam_id,
            func.count(exam_models.Question.id),
        )
        .where(exam_models.Question.exam_id.in_(exam_ids))
        .group_by(exam_models.Question.exam_id)
    ).all()
    counts_by_exam: dict[UUID, int] = {
        exam_id: int(count_val or 0) for exam_id, count_val in count_rows
    }

    attempt_rows = list(
        db.execute(
            select(attempt_models.ExamAttempt)
            .where(
                attempt_models.ExamAttempt.user_id == student_user_id,
                attempt_models.ExamAttempt.exam_id.in_(exam_ids),
            )
            .order_by(attempt_models.ExamAttempt.started_at.desc())
        ).scalars().all()
    )
    attempts_by_exam: dict[UUID, list[attempt_models.ExamAttempt]] = {}
    for attempt in attempt_rows:
        attempts_by_exam.setdefault(attempt.exam_id, []).append(attempt)

    now = _utc_now()
    return [
        _build_student_exam_out(
            exam,
            total_questions=counts_by_exam.get(exam.id, 0),
            attempts=attempts_by_exam.get(exam.id, []),
            now=now,
        )
        for exam in exams
    ]


def get_exam_student(
    db: Session,
    exam_id: UUID,
    student_user_id: UUID,
) -> ExamStudentOut:
    """Fetch a single PUBLISHED exam's instructions/metadata for a student."""
    exam = db.execute(
        select(exam_models.Exam).where(
            exam_models.Exam.id == exam_id,
            exam_models.Exam.status == "PUBLISHED",
        )
    ).scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination not found",
        )

    total_questions = _count_exam_questions(db, exam.id)
    attempts = list(
        db.execute(
            select(attempt_models.ExamAttempt)
            .where(
                attempt_models.ExamAttempt.user_id == student_user_id,
                attempt_models.ExamAttempt.exam_id == exam.id,
            )
            .order_by(attempt_models.ExamAttempt.started_at.desc())
        ).scalars().all()
    )
    return _build_student_exam_out(
        exam,
        total_questions=total_questions,
        attempts=attempts,
        now=_utc_now(),
    )
