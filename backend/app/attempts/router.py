"""FastAPI routers for student examination attempts and administrator results."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.attempts import service
from app.attempts.schemas import (
    AnswerSaveRequest,
    AnswerSaveResponse,
    AttemptDelivery,
    AttemptResultOut,
    AttemptStartRequest,
    AttemptStartResponse,
    AttemptSubmitRequest,
    AttemptSubmittedHiddenOut,
    ExamAdminResultsResponse,
    StudentAttemptSummary,
)
from app.auth.dependencies import AuthIdentity, require_admin, require_student
from app.database.session import get_db

exam_attempt_student_router = APIRouter(
    prefix="/api/exams",
    tags=["attempts"],
    dependencies=[Depends(require_student)],
)

attempts_student_router = APIRouter(
    prefix="/api/attempts",
    tags=["attempts"],
    dependencies=[Depends(require_student)],
)

student_history_router = APIRouter(
    prefix="/api/student/attempts",
    tags=["attempts"],
    dependencies=[Depends(require_student)],
)

admin_results_router = APIRouter(
    prefix="/api/admin",
    tags=["admin-results"],
    dependencies=[Depends(require_admin)],
)


# ---------------------------------------------------------------------------
# Student attempt routes
# ---------------------------------------------------------------------------


@exam_attempt_student_router.post(
    "/{exam_id}/attempts",
    response_model=AttemptStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_attempt_route(
    exam_id: UUID,
    response: Response,
    _payload: AttemptStartRequest | None = Body(default=None),
    identity: AuthIdentity = Depends(require_student),
    db: Session = Depends(get_db),
) -> AttemptStartResponse:
    student_user_id = service.require_student_user_id(identity)
    started = service.start_attempt(
        db,
        exam_id=exam_id,
        student_user_id=student_user_id,
    )
    if started.resumed:
        response.status_code = status.HTTP_200_OK
    return started


@attempts_student_router.get(
    "/{attempt_id}",
    response_model=AttemptDelivery,
)
def get_attempt_delivery_route(
    attempt_id: UUID,
    identity: AuthIdentity = Depends(require_student),
    db: Session = Depends(get_db),
) -> AttemptDelivery | JSONResponse:
    student_user_id = service.require_student_user_id(identity)
    try:
        return service.get_attempt_for_delivery(
            db,
            attempt_id=attempt_id,
            student_user_id=student_user_id,
        )
    except service.AttemptConflictException as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.error_payload)


@attempts_student_router.put(
    "/{attempt_id}/answers/{question_id}",
    response_model=AnswerSaveResponse,
)
def save_answer_route(
    attempt_id: UUID,
    question_id: UUID,
    data: AnswerSaveRequest,
    identity: AuthIdentity = Depends(require_student),
    db: Session = Depends(get_db),
) -> AnswerSaveResponse | JSONResponse:
    student_user_id = service.require_student_user_id(identity)
    try:
        return service.save_answer(
            db,
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_id=data.selected_option_id,
            student_user_id=student_user_id,
        )
    except service.AttemptConflictException as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.error_payload)


@attempts_student_router.post(
    "/{attempt_id}/submit",
    response_model=AttemptResultOut | AttemptSubmittedHiddenOut,
)
def submit_attempt_route(
    attempt_id: UUID,
    data: AttemptSubmitRequest | None = Body(default=None),
    identity: AuthIdentity = Depends(require_student),
    db: Session = Depends(get_db),
) -> AttemptResultOut | AttemptSubmittedHiddenOut:
    student_user_id = service.require_student_user_id(identity)
    confirm = True if data is None else data.confirm
    return service.submit_attempt(
        db,
        attempt_id=attempt_id,
        student_user_id=student_user_id,
        confirm=confirm,
    )


@attempts_student_router.get(
    "/{attempt_id}/result",
    response_model=AttemptResultOut | AttemptSubmittedHiddenOut,
)
def get_attempt_result_route(
    attempt_id: UUID,
    identity: AuthIdentity = Depends(require_student),
    db: Session = Depends(get_db),
) -> AttemptResultOut | AttemptSubmittedHiddenOut:
    student_user_id = service.require_student_user_id(identity)
    return service.get_attempt_result(
        db,
        attempt_id=attempt_id,
        student_user_id=student_user_id,
    )


@student_history_router.get(
    "",
    response_model=list[StudentAttemptSummary],
)
def list_student_attempts_route(
    identity: AuthIdentity = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[StudentAttemptSummary]:
    student_user_id = service.require_student_user_id(identity)
    return service.list_student_attempts(db, student_user_id=student_user_id)


# ---------------------------------------------------------------------------
# Administrator results routes
# ---------------------------------------------------------------------------


@admin_results_router.get(
    "/exams/{exam_id}/results",
    response_model=ExamAdminResultsResponse,
)
def get_admin_exam_results_route(
    exam_id: UUID,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ExamAdminResultsResponse:
    admin_user_id = service.require_admin_user_id(identity)
    return service.get_admin_exam_results(
        db,
        exam_id=exam_id,
        admin_user_id=admin_user_id,
    )


@admin_results_router.get(
    "/attempts/{attempt_id}",
    response_model=AttemptResultOut,
)
def get_admin_attempt_detail_route(
    attempt_id: UUID,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AttemptResultOut:
    admin_user_id = service.require_admin_user_id(identity)
    return service.get_admin_attempt_detail(
        db,
        attempt_id=attempt_id,
        admin_user_id=admin_user_id,
    )


router = APIRouter()
router.include_router(exam_attempt_student_router)
router.include_router(attempts_student_router)
router.include_router(student_history_router)
router.include_router(admin_results_router)
