"""FastAPI routers for Admin exam authoring/lifecycle and Student exam discovery."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import Response as BinaryResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthIdentity, require_admin, require_student
from app.database.session import get_db
from app.exams import models as exam_models
from app.exams import service
from app.exams.parser import ANSWER_KEY_ENTRY, ANSWER_KEY_ROW
from app.exams.pdf_import import (
    MAX_PDF_BYTES,
    OCRUnavailable,
    detect_pdf_questions,
    detect_questions_with_ocr,
    validate_pdf,
)
from app.exams.pdf_storage import load_image, regenerate_crops, store_pdf
from app.exams.schemas import (
    CropUpdateRequest,
    CropUpdateResponse,
    ExamAdminOut,
    ExamCreate,
    ExamStatus,
    ExamStudentOut,
    ExamUpdate,
    ExamWithQuestionsAdmin,
    ParsedOption,
    ParsedQuestion,
    ParseQuestionsError,
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


@admin_router.post("/{exam_id}/import-pdf", response_model=ParseQuestionsResponse)
async def import_pdf_route(
    exam_id: UUID,
    file: UploadFile = File(...),
    answer_key_text: str = Form(default=""),
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ParseQuestionsResponse:
    service.require_admin_user_id(identity)
    exam = db.get(exam_models.Exam, exam_id)
    if exam is None or exam.status != "DRAFT":
        raise HTTPException(status_code=404, detail="Draft examination not found")
    data = await file.read(MAX_PDF_BYTES + 1)
    try:
        doc = validate_pdf(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        detected = detect_pdf_questions(doc)
        ocr_used = len(detected) < 2
        if ocr_used:
            try:
                detected = detect_questions_with_ocr(doc)
            except OCRUnavailable as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        page_count = len(doc)
        page_dimensions = [(float(page.rect.width), float(page.rect.height)) for page in doc]
    finally:
        doc.close()
    if not detected:
        raise HTTPException(status_code=422, detail="No numbered questions were detected")
    source_id = uuid4()
    try:
        store_pdf(source_id, data, detected)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="PDF storage is unavailable") from exc
    source = exam_models.ExamSourceFile(
        id=source_id,
        exam_id=exam_id,
        original_filename=(file.filename or "uploaded.pdf")[:255],
        sha256=hashlib.sha256(data).hexdigest(),
        page_count=page_count,
    )
    db.add(source)
    db.commit()
    key: dict[int, tuple[str, Decimal]] = {}
    compact = re.sub(r"\s+", "", answer_key_text)
    if compact and re.fullmatch(r"[A-Da-d]+", compact):
        key = {i: (letter.upper(), Decimal(1)) for i, letter in enumerate(compact, 1)}
    else:
        lines = [line.strip() for line in answer_key_text.splitlines() if line.strip()]
        for i in range(len(lines) - 2):
            if (
                re.fullmatch(r"\d+", lines[i])
                and re.fullmatch(r"[A-Da-d]", lines[i + 1])
                and re.fullmatch(r"\d+", lines[i + 2])
            ):
                key[int(lines[i])] = (lines[i + 1].upper(), Decimal(lines[i + 2]))
        for line in answer_key_text.splitlines():
            row = ANSWER_KEY_ROW.fullmatch(line)
            for match in ANSWER_KEY_ENTRY.finditer(line):
                if match.group(2).upper() in "ABCD":
                    key[int(match.group(1))] = (
                        match.group(2).upper(),
                        Decimal(row.group(3)) if row and row.group(3) else Decimal(1),
                    )
    mismatch = bool(answer_key_text.strip()) and (
        len(key) != len(detected) or set(key) != {question.number for question in detected}
    )
    items: list[ParsedQuestion] = []
    for question in detected:
        answer = key.get(question.number)
        warnings = list(question.warnings)
        if answer is None:
            warnings.append("No answer in the key; select one before saving.")
        items.append(
            ParsedQuestion(
                position=question.number,
                question_text=question.extracted_text or f"Question {question.number}",
                source_file_id=source_id,
                source_number=question.number,
                image_urls=[
                    f"/api/admin/exams/{exam_id}/source-images/{source_id}/{question.number}/{i}"
                    for i in range(len(question.regions))
                ],
                image_regions=[
                    {"page": region.page, "bbox": list(region.bbox)} for region in question.regions
                ],
                options=[
                    ParsedOption(label=letter, option_text=f"Option {letter} (see image)")
                    for letter in "ABCD"
                ],
                answer_label=answer[0] if answer else None,
                points=answer[1] if answer else Decimal(1),
                valid=answer is not None and not mismatch,
                warnings=warnings,
                pdf_options_text=question.options_text,
                pdf_confidence=(
                    Decimal("0.50")
                    if ocr_used
                    else Decimal("1.00")
                    if len(question.options_text) == 4
                    else Decimal("0.75")
                ),
            )
        )
    return ParseQuestionsResponse(
        valid_questions=[q for q in items if q.valid],
        invalid_questions=[q for q in items if not q.valid],
        total_blocks=len(items),
        valid_count=sum(q.valid for q in items),
        errors=(
            [
                ParseQuestionsError(
                    block_index=0,
                    message=(
                        f"Answer key has {len(key)} answers but {len(detected)} "
                        "questions were detected"
                    ),
                )
            ]
            if mismatch
            else []
        ),
        error_count=1 if mismatch else 0,
        normalized_answer_key=", ".join(f"{n}. {v[0]}" for n, v in sorted(key.items())),
        page_dimensions=page_dimensions,
        ocr_used=ocr_used,
    )


@admin_router.get("/{exam_id}/source-images/{source_id}/{number}/{index}")
def admin_source_image_route(
    exam_id: UUID,
    source_id: UUID,
    number: int,
    index: int,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BinaryResponse:
    service.require_admin_user_id(identity)
    source = db.get(exam_models.ExamSourceFile, source_id)
    if source is not None and source.exam_id != exam_id:
        source = None
    if source is None:
        raise HTTPException(status_code=404, detail="Image not found")
    try:
        image = load_image(source.id, number, index)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Image not found") from exc
    return BinaryResponse(content=image, media_type="image/png")


@admin_router.put(
    "/{exam_id}/sources/{source_id}/questions/{number}/crops",
    response_model=CropUpdateResponse,
)
def update_question_crops_route(
    exam_id: UUID,
    source_id: UUID,
    number: int,
    payload: CropUpdateRequest,
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CropUpdateResponse:
    service.require_admin_user_id(identity)
    exam = db.get(exam_models.Exam, exam_id)
    source = db.get(exam_models.ExamSourceFile, source_id)
    if exam is None or exam.status != "DRAFT" or source is None or source.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="Draft PDF source not found")
    try:
        regions = regenerate_crops(
            source_id,
            number,
            [region.model_dump() for region in payload.regions],
            dpi=payload.dpi,
            padding=payload.padding,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    questions = (
        db.query(exam_models.Question)
        .filter_by(exam_id=exam_id, source_file_id=source_id, source_number=number)
        .all()
    )
    for question in questions:
        question.image_regions = json.dumps(regions)
        question.image_paths = json.dumps(
            [f"{number}-{index}.png" for index in range(len(regions))]
        )
    db.commit()
    version = uuid4().hex
    return CropUpdateResponse(
        regions=regions,
        image_urls=[
            f"/api/admin/exams/{exam_id}/source-images/{source_id}/{number}/{index}?v={version}"
            for index in range(len(regions))
        ],
    )


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
    questions = payload.questions if isinstance(payload, SaveQuestionsRequest) else payload
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
