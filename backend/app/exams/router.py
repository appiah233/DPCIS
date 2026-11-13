"""FastAPI routers for Admin exam authoring/lifecycle and Student exam discovery."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthIdentity, require_admin, require_student
from app.database.session import get_db
from app.exams import service
from app.exams.schemas import (
    ExamAdminOut,
    ExamCreate,
    ExamStatus,
    ExamStudentOut,
    ExamUpdate,
    ExamWithQuestionsAdmin,
    ParseQuestionsRequest,
    ParseQuestionsResponse,
    QuestionAdminOut,
    QuestionCreate,
    SaveQuestionsRequest,
)

admin_router = APIRouter(
    prefix="/api/admin/exams",
    tags=["admin-exams"],
    dependencies=[Depends(require_admin)],
)

student_router = APIRouter(
    prefix="/api/exams",
    tags=["exams"],
    dependencies=[Depends(require_student)],
)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------


@admin_router.post(
    "",
    response_model=ExamAdminOut,
    status_code=status.HTTP_201_CREATED,
)
def create_exam_route(
    data: ExamCreate,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ExamAdminOut:
    return service.create_exam(db, identity, data)


@admin_router.get(
    "",
    response_model=list[ExamAdminOut],
)
def list_exams_admin_route(
    status_filter: ExamStatus | None = Query(default=None, alias="status"),
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ExamAdminOut]:
    return service.list_exams_admin(db, identity, status_filter=status_filter)


@admin_router.post(
    "/parse-questions",
    response_model=ParseQuestionsResponse,
)
def parse_questions_route(
    data: ParseQuestionsRequest,
    identity: AuthIdentity = Depends(require_admin),
) -> ParseQuestionsResponse:
    service.require_admin_user_id(identity)
    return service.parse_questions_service(data.raw_text, data.answer_key_text)


@admin_router.get(
    "/{exam_id}",
    response_model=ExamWithQuestionsAdmin,
)
def get_exam_admin_route(
    exam_id: UUID,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ExamWithQuestionsAdmin:
    return service.get_exam_admin(db, exam_id, identity)


@admin_router.patch(
    "/{exam_id}",
    response_model=ExamAdminOut,
)
def update_exam_route(
    exam_id: UUID,
    data: ExamUpdate,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ExamAdminOut:
    return service.update_exam(db, exam_id, identity, data)


@admin_router.delete(
    "/{exam_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_exam_route(
    exam_id: UUID,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_exam(db, exam_id, identity)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.put(
    "/{exam_id}/questions",
    response_model=ExamWithQuestionsAdmin,
)
def save_questions_route(
    exam_id: UUID,
    payload: SaveQuestionsRequest | list[QuestionCreate],
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ExamWithQuestionsAdmin:
    questions = (
        payload.questions if isinstance(payload, SaveQuestionsRequest) else payload
    )
    return service.save_questions(db, exam_id, identity, questions)


@admin_router.post(
    "/{exam_id}/questions",
    response_model=QuestionAdminOut,
    status_code=status.HTTP_201_CREATED,
)
def add_question_route(
    exam_id: UUID,
    data: QuestionCreate,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuestionAdminOut:
    return service.add_question(db, exam_id, identity, data)


@admin_router.put(
    "/{exam_id}/questions/{question_id}",
    response_model=QuestionAdminOut,
)
def update_question_route(
    exam_id: UUID,
    question_id: UUID,
    data: QuestionCreate,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuestionAdminOut:
    return service.update_question(db, exam_id, question_id, identity, data)


@admin_router.delete(
    "/{exam_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_question_route(
    exam_id: UUID,
    question_id: UUID,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_question(db, exam_id, question_id, identity)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post(
    "/{exam_id}/publish",
    response_model=ExamAdminOut,
)
def publish_exam_route(
    exam_id: UUID,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ExamAdminOut:
    return service.publish_exam(db, exam_id, identity)


@admin_router.post(
    "/{exam_id}/close",
    response_model=ExamAdminOut,
)
def close_exam_route(
    exam_id: UUID,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ExamAdminOut:
    return service.close_exam(db, exam_id, identity)


# ---------------------------------------------------------------------------
# Student routes
# ---------------------------------------------------------------------------


@student_router.get(
    "",
    response_model=list[ExamStudentOut],
)
def list_available_exams_route(
    identity: AuthIdentity = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[ExamStudentOut]:
    student_user_id = service.require_student_user_id(identity)
    return service.list_available_exams(db, student_user_id)


@student_router.get(
    "/{exam_id}",
    response_model=ExamStudentOut,
)
def get_exam_student_route(
    exam_id: UUID,
    identity: AuthIdentity = Depends(require_student),
    db: Session = Depends(get_db),
) -> ExamStudentOut:
    student_user_id = service.require_student_user_id(identity)
    return service.get_exam_student(db, exam_id, student_user_id)


router = APIRouter()
router.include_router(admin_router)
router.include_router(student_router)
