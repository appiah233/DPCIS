"""Comprehensive tests for server-authoritative timer and deterministic MCQ grading."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.database  # noqa: F401  # Registers all SQLAlchemy models on Base.metadata
from app.attempts.grading import (
    GradeComputation,
    QuestionOutcome,
    build_correct_map,
    build_question_review,
    can_view_correct_answers,
    can_view_student_result,
    compute_exam_results_summary,
    compute_expires_at,
    compute_mcq_grade,
    ensure_utc,
    finalize_attempt_locked,
    is_expired,
    project_persisted_result,
    resolve_submission_reason,
    utc_now,
)
from app.attempts.models import AttemptQuestion, ExamAttempt, StudentAnswer
from app.database.base import Base
from app.exams.models import Exam, Question, QuestionOption
from app.users.models import ApplicationUser


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Provide an isolated in-memory SQLite session with foreign keys enabled."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_option_stub(
    option_id: UUID | None = None,
    *,
    is_correct: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(id=option_id or uuid4(), is_correct=is_correct)


def _make_question_stub(
    question_id: UUID | None = None,
    *,
    points: Decimal = Decimal("1.00"),
) -> SimpleNamespace:
    return SimpleNamespace(question_id=question_id or uuid4(), points=points)


def _seed_exam_with_questions(
    db: Session,
    *,
    pass_mark: Decimal = Decimal("50.00"),
    duration_minutes: int = 30,
    show_result: bool = True,
    show_correct_answers: bool = False,
    question_specs: list[tuple[Decimal, str]] | None = None,
) -> tuple[
    ApplicationUser,
    ApplicationUser,
    Exam,
    list[tuple[Question, dict[str, QuestionOption]]],
]:
    """Seed admin, student, published exam, and questions with options A-D."""
    admin = ApplicationUser(
        id=uuid4(),
        auth_subject=f"admin-{uuid4()}",
        email="admin@example.edu",
        display_name="Exam Admin",
        role="ADMIN",
    )
    student = ApplicationUser(
        id=uuid4(),
        auth_subject=f"student-{uuid4()}",
        email="student@example.edu",
        display_name="Exam Student",
        role="STUDENT",
    )
    db.add_all([admin, student])
    db.flush()

    exam = Exam(
        id=uuid4(),
        title="Midterm Assessment",
        duration_minutes=duration_minutes,
        pass_mark=pass_mark,
        max_attempts=3,
        show_result=show_result,
        show_correct_answers=show_correct_answers,
        status="PUBLISHED",
        created_by=admin.id,
    )
    db.add(exam)
    db.flush()

    specs = question_specs or [
        (Decimal("1.00"), "A"),
        (Decimal("2.00"), "B"),
        (Decimal("1.00"), "C"),
    ]
    seeded_questions: list[tuple[Question, dict[str, QuestionOption]]] = []
    for position, (points, correct_label) in enumerate(specs, start=1):
        question = Question(
            id=uuid4(),
            exam_id=exam.id,
            question_text=f"Question {position}",
            position=position,
            points=points,
        )
        db.add(question)
        db.flush()

        option_map: dict[str, QuestionOption] = {}
        for opt_pos, label in enumerate(("A", "B", "C", "D")):
            option = QuestionOption(
                id=uuid4(),
                question_id=question.id,
                label=label,
                option_text=f"Option {label}",
                is_correct=(label == correct_label),
                position=opt_pos,
            )
            db.add(option)
            option_map[label] = option
        seeded_questions.append((question, option_map))

    db.commit()
    return admin, student, exam, seeded_questions


def _create_attempt(
    db: Session,
    *,
    exam: Exam,
    student: ApplicationUser,
    questions: list[Question],
    started_at: datetime,
    selected_by_question: dict[UUID, UUID | None],
) -> ExamAttempt:
    attempt = ExamAttempt(
        id=uuid4(),
        exam_id=exam.id,
        user_id=student.id,
        started_at=ensure_utc(started_at),
        expires_at=compute_expires_at(started_at, exam.duration_minutes),
        status="IN_PROGRESS",
        total_questions=len(questions),
    )
    db.add(attempt)
    db.flush()

    for idx, question in enumerate(questions):
        db.add(
            AttemptQuestion(
                attempt_id=attempt.id,
                question_id=question.id,
                display_order=idx,
            )
        )
        if question.id in selected_by_question:
            db.add(
                StudentAnswer(
                    id=uuid4(),
                    attempt_id=attempt.id,
                    question_id=question.id,
                    selected_option_id=selected_by_question[question.id],
                    answered_at=ensure_utc(started_at),
                    updated_at=ensure_utc(started_at),
                )
            )
    db.commit()
    return attempt


# ---------------------------------------------------------------------------
# Timer & UTC boundary tests
# ---------------------------------------------------------------------------


def test_utc_now_and_ensure_utc_normalization() -> None:
    now = utc_now()
    assert now.tzinfo == UTC

    naive = datetime(2026, 11, 11, 14, 30, 0)
    normalized_naive = ensure_utc(naive)
    assert normalized_naive == datetime(2026, 11, 11, 14, 30, 0, tzinfo=UTC)

    plus_two = timezone(timedelta(hours=2))
    aware_offset = datetime(2026, 11, 11, 16, 30, 0, tzinfo=plus_two)
    assert ensure_utc(aware_offset) == datetime(2026, 11, 11, 14, 30, 0, tzinfo=UTC)


def test_compute_expires_at_and_boundary_expiry_checks() -> None:
    started = datetime(2026, 11, 11, 10, 0, 0, tzinfo=UTC)
    expires = compute_expires_at(started, 45)
    assert expires == datetime(2026, 11, 11, 10, 45, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="duration_minutes"):
        compute_expires_at(started, 0)

    # Just before deadline -> active
    assert is_expired(expires, now=expires - timedelta(microseconds=1)) is False
    # Exact deadline -> expired (now >= expires_at)
    assert is_expired(expires, now=expires) is True
    # After deadline -> expired
    assert is_expired(expires, now=expires + timedelta(seconds=1)) is True


def test_is_expired_normalizes_naive_sqlite_datetimes() -> None:
    naive_expires = datetime(2026, 11, 11, 10, 45, 0)
    aware_before = datetime(2026, 11, 11, 10, 44, 59, tzinfo=UTC)
    aware_equal = datetime(2026, 11, 11, 10, 45, 0, tzinfo=UTC)
    aware_after = datetime(2026, 11, 11, 10, 45, 1, tzinfo=UTC)

    assert is_expired(naive_expires, now=aware_before) is False
    assert is_expired(naive_expires, now=aware_equal) is True
    assert is_expired(naive_expires, now=aware_after) is True


def test_resolve_submission_reason_enforces_server_deadline() -> None:
    expires = datetime(2026, 11, 11, 12, 0, 0, tzinfo=UTC)

    assert (
        resolve_submission_reason(
            expires,
            requested_reason="STUDENT_SUBMITTED",
            now=expires - timedelta(seconds=1),
        )
        == "STUDENT_SUBMITTED"
    )
    # Submitting at or past expires_at is authoritatively TIMER_EXPIRED.
    assert (
        resolve_submission_reason(
            expires,
            requested_reason="STUDENT_SUBMITTED",
            now=expires,
        )
        == "TIMER_EXPIRED"
    )
    assert (
        resolve_submission_reason(
            expires,
            requested_reason="STUDENT_SUBMITTED",
            now=expires + timedelta(minutes=5),
        )
        == "TIMER_EXPIRED"
    )


# ---------------------------------------------------------------------------
# Pure deterministic Decimal grading tests
# ---------------------------------------------------------------------------


def test_compute_mcq_grade_all_correct_partial_wrong_and_unanswered() -> None:
    q1 = _make_question_stub(points=Decimal("1.25"))
    q2 = _make_question_stub(points=Decimal("2.50"))
    q3 = _make_question_stub(points=Decimal("1.25"))
    q4 = _make_question_stub(points=Decimal("5.00"))

    o1_ok, o1_bad = _make_option_stub(is_correct=True), _make_option_stub()
    o2_bad, o2_ok = _make_option_stub(), _make_option_stub(is_correct=True)
    o3_ok, o3_bad = _make_option_stub(is_correct=True), _make_option_stub()
    o4_ok, o4_bad = _make_option_stub(is_correct=True), _make_option_stub()

    options = {
        q1.question_id: [o1_ok, o1_bad],
        q2.question_id: [o2_bad, o2_ok],
        q3.question_id: [o3_ok, o3_bad],
        q4.question_id: [o4_ok, o4_bad],
    }

    # All correct
    all_correct = compute_mcq_grade(
        attempt_questions=[q1, q2, q3, q4],
        options_by_question=options,
        answers_by_question={
            q1.question_id: o1_ok.id,
            q2.question_id: o2_ok.id,
            q3.question_id: o3_ok.id,
            q4.question_id: o4_ok.id,
        },
        pass_mark=Decimal("60.00"),
    )
    assert isinstance(all_correct, GradeComputation)
    assert all_correct.total_questions == 4
    assert all_correct.correct_answers == 4
    assert all_correct.incorrect_answers == 0
    assert all_correct.unanswered_questions == 0
    assert all_correct.points_earned == Decimal("10.00")
    assert all_correct.points_available == Decimal("10.00")
    assert all_correct.percentage == Decimal("100.00")
    assert all_correct.passed is True
    assert len(all_correct.question_outcomes) == 4
    assert all(
        isinstance(o, QuestionOutcome) and o.is_correct
        for o in all_correct.question_outcomes
    )

    # All wrong
    all_wrong = compute_mcq_grade(
        attempt_questions=[q1, q2, q3, q4],
        options_by_question=options,
        answers_by_question={
            q1.question_id: o1_bad.id,
            q2.question_id: o2_bad.id,
            q3.question_id: o3_bad.id,
            q4.question_id: o4_bad.id,
        },
        pass_mark=Decimal("50.00"),
    )
    assert all_wrong.correct_answers == 0
    assert all_wrong.incorrect_answers == 4
    assert all_wrong.unanswered_questions == 0
    assert all_wrong.points_earned == Decimal("0.00")
    assert all_wrong.points_available == Decimal("10.00")
    assert all_wrong.percentage == Decimal("0.00")
    assert all_wrong.passed is False

    # Partial + explicit None cleared selection + missing key unanswered
    partial = compute_mcq_grade(
        attempt_questions=[q1, q2, q3, q4],
        options_by_question=options,
        answers_by_question={
            q1.question_id: o1_ok.id,   # +1.25 (correct)
            q2.question_id: o2_ok.id,   # +2.50 (correct)
            q3.question_id: o3_bad.id,  # +0.00 (incorrect)
            q4.question_id: None,       # +0.00 (cleared -> unanswered)
        },
        pass_mark=Decimal("37.50"),
    )
    assert partial.correct_answers == 2
    assert partial.incorrect_answers == 1
    assert partial.unanswered_questions == 1
    assert partial.points_earned == Decimal("3.75")
    assert partial.points_available == Decimal("10.00")
    assert partial.percentage == Decimal("37.50")
    assert partial.passed is True

    # All unanswered
    unanswered = compute_mcq_grade(
        attempt_questions=[q1, q2],
        options_by_question=options,
        answers_by_question={},
        pass_mark=Decimal("1.00"),
    )
    assert unanswered.correct_answers == 0
    assert unanswered.incorrect_answers == 0
    assert unanswered.unanswered_questions == 2
    assert unanswered.points_earned == Decimal("0.00")
    assert unanswered.percentage == Decimal("0.00")
    assert unanswered.passed is False


def test_compute_mcq_grade_repeating_decimals_and_midpoint_round_half_up() -> None:
    q1 = _make_question_stub(points=Decimal("1.00"))
    q2 = _make_question_stub(points=Decimal("1.00"))
    q3 = _make_question_stub(points=Decimal("1.00"))
    o1_ok, o1_bad = _make_option_stub(is_correct=True), _make_option_stub()
    o2_ok, o2_bad = _make_option_stub(is_correct=True), _make_option_stub()
    o3_ok, o3_bad = _make_option_stub(is_correct=True), _make_option_stub()
    opts = {
        q1.question_id: [o1_ok, o1_bad],
        q2.question_id: [o2_ok, o2_bad],
        q3.question_id: [o3_ok, o3_bad],
    }

    one_third = compute_mcq_grade(
        attempt_questions=[q1, q2, q3],
        options_by_question=opts,
        answers_by_question={q1.question_id: o1_ok.id},
        pass_mark=Decimal("33.34"),
    )
    assert one_third.percentage == Decimal("33.33")
    assert one_third.passed is False

    two_thirds = compute_mcq_grade(
        attempt_questions=[q1, q2, q3],
        options_by_question=opts,
        answers_by_question={q1.question_id: o1_ok.id, q2.question_id: o2_ok.id},
        pass_mark=Decimal("66.67"),
    )
    assert two_thirds.percentage == Decimal("66.67")
    assert two_thirds.passed is True

    # Midpoint 24.69 / 200.00 * 100 = 12.345 -> ROUND_HALF_UP => 12.35 (not 12.34 half-even)
    qa = _make_question_stub(points=Decimal("24.69"))
    qb = _make_question_stub(points=Decimal("175.31"))
    oa_ok = _make_option_stub(is_correct=True)
    ob_ok = _make_option_stub(is_correct=True)
    midpoint = compute_mcq_grade(
        attempt_questions=[qa, qb],
        options_by_question={qa.question_id: [oa_ok], qb.question_id: [ob_ok]},
        answers_by_question={qa.question_id: oa_ok.id},
        pass_mark=Decimal("12.35"),
    )
    assert midpoint.points_earned == Decimal("24.69")
    assert midpoint.points_available == Decimal("200.00")
    assert midpoint.percentage == Decimal("12.35")
    assert midpoint.passed is True

    # Exact pass_mark boundary minus 0.01 fails
    just_below = compute_mcq_grade(
        attempt_questions=[qa, qb],
        options_by_question={qa.question_id: [oa_ok], qb.question_id: [ob_ok]},
        answers_by_question={qa.question_id: oa_ok.id},
        pass_mark=Decimal("12.36"),
    )
    assert just_below.percentage == Decimal("12.35")
    assert just_below.passed is False


def test_compute_mcq_grade_edge_cases_and_integrity_guards() -> None:
    # Zero questions -> 0.00% without ZeroDivisionError
    empty_grade = compute_mcq_grade(
        attempt_questions=[],
        options_by_question={},
        answers_by_question={},
        pass_mark=Decimal("0.00"),
    )
    assert empty_grade.total_questions == 0
    assert empty_grade.points_available == Decimal("0.00")
    assert empty_grade.percentage == Decimal("0.00")
    assert empty_grade.passed is True

    q1 = _make_question_stub(points=Decimal("2.00"))
    q_other = _make_question_stub(points=Decimal("2.00"))
    o1_ok = _make_option_stub(is_correct=True)
    o_other_ok = _make_option_stub(is_correct=True)

    # Orphan answer outside snapshot + cross-question option tampering
    tampered = compute_mcq_grade(
        attempt_questions=[q1],
        options_by_question={q1.question_id: [o1_ok]},
        answers_by_question={
            q1.question_id: o_other_ok.id,      # belongs to a different question -> incorrect
            q_other.question_id: o_other_ok.id,  # orphan question -> ignored
        },
        pass_mark=Decimal("50.00"),
    )
    assert tampered.total_questions == 1
    assert tampered.correct_answers == 0
    assert tampered.incorrect_answers == 1
    assert tampered.points_earned == Decimal("0.00")
    assert tampered.question_outcomes[0].is_correct is False

    # Question with zero options marked is_correct -> correct_option_id is None, awards 0
    no_key = compute_mcq_grade(
        attempt_questions=[q1],
        options_by_question={q1.question_id: [_make_option_stub(is_correct=False)]},
        answers_by_question={q1.question_id: o1_ok.id},
        pass_mark=Decimal("50.00"),
    )
    assert no_key.question_outcomes[0].correct_option_id is None
    assert no_key.incorrect_answers == 1
    assert no_key.points_earned == Decimal("0.00")

    # Multiple options marked is_correct -> fail closed
    with pytest.raises(ValueError, match="multiple options marked as correct"):
        compute_mcq_grade(
            attempt_questions=[q1],
            options_by_question={
                q1.question_id: [
                    _make_option_stub(is_correct=True),
                    _make_option_stub(is_correct=True),
                ]
            },
            answers_by_question={},
            pass_mark=Decimal("50.00"),
        )


# ---------------------------------------------------------------------------
# Database integration: finalization, immutability, disclosure, summary
# ---------------------------------------------------------------------------


def test_finalize_attempt_locked_identical_scores_and_immutability(db_session: Session) -> None:
    _admin, student, exam, seeded = _seed_exam_with_questions(
        db_session,
        pass_mark=Decimal("50.00"),
        duration_minutes=30,
        show_result=True,
        show_correct_answers=True,
        question_specs=[
            (Decimal("1.50"), "A"),
            (Decimal("2.50"), "B"),
            (Decimal("1.00"), "C"),
        ],
    )
    questions = [q for q, _ in seeded]
    q1, opts1 = seeded[0]
    q2, opts2 = seeded[1]
    q3, opts3 = seeded[2]

    t_start = datetime(2026, 11, 11, 9, 0, 0, tzinfo=UTC)
    selected = {
        q1.id: opts1["A"].id,  # correct (+1.50)
        q2.id: opts2["C"].id,  # wrong (+0.00)
        q3.id: opts3["C"].id,  # correct (+1.00)
    }  # 2.50 / 5.00 = 50.00% -> passed=True

    attempt_manual = _create_attempt(
        db_session,
        exam=exam,
        student=student,
        questions=questions,
        started_at=t_start,
        selected_by_question=selected,
    )
    t_manual = t_start + timedelta(minutes=12)
    finalized_manual, did_finalize = finalize_attempt_locked(
        db_session,
        attempt_manual,
        exam,
        reason="STUDENT_SUBMITTED",
        now=t_manual,
    )
    db_session.commit()

    assert did_finalize is True
    assert finalized_manual.status == "GRADED"
    assert finalized_manual.submission_reason == "STUDENT_SUBMITTED"
    assert ensure_utc(finalized_manual.submitted_at) == t_manual
    assert finalized_manual.total_questions == 3
    assert finalized_manual.correct_answers == 2
    assert finalized_manual.incorrect_answers == 1
    assert finalized_manual.unanswered_questions == 0
    assert finalized_manual.points_earned == Decimal("2.50")
    assert finalized_manual.points_available == Decimal("5.00")
    assert finalized_manual.percentage == Decimal("50.00")
    assert finalized_manual.passed is True

    # Second attempt with identical answers finalized via TIMER_EXPIRED yields identical scores
    attempt_expired = _create_attempt(
        db_session,
        exam=exam,
        student=student,
        questions=questions,
        started_at=t_start + timedelta(hours=1),
        selected_by_question=selected,
    )
    t_expire = t_start + timedelta(hours=1, minutes=30)
    finalized_expired, did_finalize_exp = finalize_attempt_locked(
        db_session,
        attempt_expired,
        exam,
        reason="TIMER_EXPIRED",
        now=t_expire,
    )
    db_session.commit()

    assert did_finalize_exp is True
    assert finalized_expired.submission_reason == "TIMER_EXPIRED"
    assert finalized_expired.points_earned == finalized_manual.points_earned
    assert finalized_expired.points_available == finalized_manual.points_available
    assert finalized_expired.percentage == finalized_manual.percentage
    assert finalized_expired.passed == finalized_manual.passed
    assert finalized_expired.correct_answers == finalized_manual.correct_answers
    assert finalized_expired.incorrect_answers == finalized_manual.incorrect_answers
    assert finalized_expired.unanswered_questions == finalized_manual.unanswered_questions

    # Mutate underlying question points and answer key AFTER grading to verify immutability
    q1.points = Decimal("99.00")
    opts1["A"].is_correct = False
    db_session.flush()
    opts1["D"].is_correct = True
    db_session.commit()

    # Re-calling finalize_attempt_locked must be a no-op returning (attempt, False)
    re_finalized, did_refinalize = finalize_attempt_locked(
        db_session,
        finalized_manual,
        exam,
        reason="TIMER_EXPIRED",
        now=t_manual + timedelta(minutes=5),
    )
    assert did_refinalize is False
    assert re_finalized.submission_reason == "STUDENT_SUBMITTED"
    assert ensure_utc(re_finalized.submitted_at) == t_manual
    assert re_finalized.points_earned == Decimal("2.50")
    assert re_finalized.points_available == Decimal("5.00")
    assert re_finalized.percentage == Decimal("50.00")
    assert re_finalized.passed is True

    projected = project_persisted_result(re_finalized)
    assert projected.points_earned == Decimal("2.50")
    assert projected.percentage == Decimal("50.00")
    assert projected.passed is True


def test_post_submission_answer_key_disclosure_gating(db_session: Session) -> None:
    _admin, student, exam, seeded = _seed_exam_with_questions(
        db_session,
        pass_mark=Decimal("50.00"),
        show_result=True,
        show_correct_answers=True,
    )
    questions = [q for q, _ in seeded]
    q1, opts1 = seeded[0]

    attempt = _create_attempt(
        db_session,
        exam=exam,
        student=student,
        questions=questions,
        started_at=datetime(2026, 11, 11, 11, 0, 0, tzinfo=UTC),
        selected_by_question={q1.id: opts1["A"].id},
    )

    # Active IN_PROGRESS attempt must NEVER leak answer keys (RULE 10)
    assert can_view_student_result(attempt, exam) is False
    assert can_view_correct_answers(attempt, exam) is False
    assert build_correct_map(db_session, attempt, exam) == {}
    assert build_question_review(db_session, attempt, exam) is None
    assert build_question_review(db_session, attempt, exam, is_admin=True) is None

    finalize_attempt_locked(db_session, attempt, exam, reason="STUDENT_SUBMITTED")
    db_session.commit()

    # With show_result=True & show_correct_answers=True after GRADED -> permitted
    assert can_view_student_result(attempt, exam) is True
    assert can_view_correct_answers(attempt, exam) is True
    correct_map = build_correct_map(db_session, attempt, exam)
    expected_map = {
        q.id: next(o.id for o in opts.values() if o.is_correct)
        for q, opts in seeded
    }
    assert correct_map == expected_map
    review = build_question_review(db_session, attempt, exam)
    assert review is not None and len(review) == 3

    # With show_correct_answers=False -> score ok, answer key blocked for student
    exam.show_correct_answers = False
    db_session.commit()
    assert can_view_student_result(attempt, exam) is True
    assert can_view_correct_answers(attempt, exam) is False
    assert build_correct_map(db_session, attempt, exam) == {}
    assert build_question_review(db_session, attempt, exam) is None
    assert build_question_review(db_session, attempt, exam, is_admin=True) is not None

    # With show_result=False & show_correct_answers=True -> both score and answer key blocked
    exam.show_result = False
    exam.show_correct_answers = True
    db_session.commit()
    assert can_view_student_result(attempt, exam) is False
    assert can_view_correct_answers(attempt, exam) is False
    assert build_correct_map(db_session, attempt, exam) == {}
    assert build_question_review(db_session, attempt, exam) is None
    assert build_question_review(db_session, attempt, exam, is_admin=True) is not None


def test_compute_exam_results_summary_zero_and_multiple_attempts(db_session: Session) -> None:
    # Zero attempts -> all summary metrics None
    empty_summary = compute_exam_results_summary([])
    assert empty_summary == {
        "completed_attempts": 0,
        "average_percentage": None,
        "highest_percentage": None,
        "lowest_percentage": None,
        "pass_rate": None,
    }

    _admin, student, exam, seeded = _seed_exam_with_questions(
        db_session,
        pass_mark=Decimal("50.00"),
        question_specs=[
            (Decimal("1.00"), "A"),
            (Decimal("1.00"), "B"),
            (Decimal("1.00"), "C"),
        ],
    )
    questions = [q for q, _ in seeded]
    q1, opts1 = seeded[0]
    q2, opts2 = seeded[1]
    q3, opts3 = seeded[2]

    t0 = datetime(2026, 11, 11, 8, 0, 0, tzinfo=UTC)
    student_active = ApplicationUser(
        id=uuid4(),
        auth_subject=f"student-active-{uuid4()}",
        email="active@example.edu",
        display_name="Active Student",
        role="STUDENT",
    )
    db_session.add(student_active)
    db_session.flush()

    in_progress = _create_attempt(
        db_session,
        exam=exam,
        student=student_active,
        questions=questions,
        started_at=t0,
        selected_by_question={},
    )
    # Only IN_PROGRESS attempt -> still 0 completed
    assert compute_exam_results_summary([in_progress]) == empty_summary

    # Graded #1: 3/3 = 100.00% (passed)
    finalize_attempt_locked(
        db_session,
        _create_attempt(
            db_session,
            exam=exam,
            student=student,
            questions=questions,
            started_at=t0 + timedelta(hours=1),
            selected_by_question={
                q1.id: opts1["A"].id,
                q2.id: opts2["B"].id,
                q3.id: opts3["C"].id,
            },
        ),
        exam,
        reason="STUDENT_SUBMITTED",
    )
    db_session.commit()

    # Graded #2: 2/3 = 66.67% (passed)
    finalize_attempt_locked(
        db_session,
        _create_attempt(
            db_session,
            exam=exam,
            student=student,
            questions=questions,
            started_at=t0 + timedelta(hours=2),
            selected_by_question={
                q1.id: opts1["A"].id,
                q2.id: opts2["B"].id,
                q3.id: opts3["A"].id,
            },
        ),
        exam,
        reason="TIMER_EXPIRED",
    )
    db_session.commit()

    # Graded #3: 1/3 = 33.33% (failed)
    finalize_attempt_locked(
        db_session,
        _create_attempt(
            db_session,
            exam=exam,
            student=student,
            questions=questions,
            started_at=t0 + timedelta(hours=3),
            selected_by_question={q1.id: opts1["A"].id},
        ),
        exam,
        reason="STUDENT_SUBMITTED",
    )
    db_session.commit()

    all_attempts = db_session.query(ExamAttempt).filter(ExamAttempt.exam_id == exam.id).all()
    summary = compute_exam_results_summary(all_attempts)
    # (100.00 + 66.67 + 33.33) / 3 = 200.00 / 3 = 66.67; 2/3 passed = 66.67%
    assert summary == {
        "completed_attempts": 3,
        "average_percentage": Decimal("66.67"),
        "highest_percentage": Decimal("100.00"),
        "lowest_percentage": Decimal("33.33"),
        "pass_rate": Decimal("66.67"),
    }


def test_sqlite_reloaded_naive_timer_and_cleared_db_answer(db_session: Session) -> None:
    admin, student, exam, seeded = _seed_exam_with_questions(
        db_session,
        duration_minutes=15,
        pass_mark=Decimal("50.00"),
    )
    questions = [q for q, _ in seeded]
    q1, opts1 = seeded[0]
    q2, _opts2 = seeded[1]

    t_start = datetime(2026, 11, 11, 13, 0, 0, tzinfo=UTC)
    attempt = _create_attempt(
        db_session,
        exam=exam,
        student=student,
        questions=questions,
        started_at=t_start,
        selected_by_question={
            q1.id: opts1["A"].id,  # +1.00
            q2.id: None,           # cleared DB row -> unanswered
        },
    )
    attempt_id = attempt.id
    db_session.expire_all()
    reloaded = db_session.get(ExamAttempt, attempt_id)
    assert reloaded is not None

    expected_expiry = t_start + timedelta(minutes=15)
    assert is_expired(reloaded.expires_at, now=expected_expiry - timedelta(seconds=1)) is False
    assert is_expired(reloaded.expires_at, now=expected_expiry) is True

    finalized, did_finalize = finalize_attempt_locked(
        db_session,
        reloaded,
        exam,
        reason="TIMER_EXPIRED",
        now=expected_expiry,
    )
    db_session.commit()
    assert did_finalize is True
    assert finalized.correct_answers == 1
    assert finalized.incorrect_answers == 0
    assert finalized.unanswered_questions == 2
    assert finalized.points_earned == Decimal("1.00")
    assert finalized.points_available == Decimal("4.00")
    assert finalized.percentage == Decimal("25.00")
    assert finalized.passed is False

    # Mismatched exam fails closed
    other_exam = Exam(
        id=uuid4(),
        title="Other Exam",
        duration_minutes=10,
        pass_mark=Decimal("50.00"),
        max_attempts=1,
        status="DRAFT",
        created_by=admin.id,
    )
    db_session.add(other_exam)
    db_session.flush()
    fresh_attempt = _create_attempt(
        db_session,
        exam=exam,
        student=student,
        questions=questions,
        started_at=t_start + timedelta(hours=1),
        selected_by_question={},
    )
    with pytest.raises(ValueError, match="does not match"):
        finalize_attempt_locked(
            db_session,
            fresh_attempt,
            other_exam,
            reason="STUDENT_SUBMITTED",
        )
