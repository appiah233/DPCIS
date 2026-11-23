"""FastAPI routers for Admin exam authoring/lifecycle and Student exam discovery."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
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
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response as BinaryResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthIdentity, require_admin, require_student
from app.config import get_settings
from app.database.session import get_db
from app.exams import models as exam_models
from app.exams import service
from app.exams.parser import ANSWER_KEY_ENTRY, ANSWER_KEY_ROW
from app.exams.pdf_import import (
    OCRUnavailable,
    detect_pdf_questions,
    detect_questions_with_ocr,
    detect_scan_questions,
    open_question_upload,
    validate_pdf,
)
from app.exams.pdf_recrop import router as recrop_router
from app.exams.pdf_storage import (
    delete_source_dir,
    has_reviewed_crop,
    load_image,
    load_regions,
    regenerate_crops,
    render_source_page,
    source_dir,
    store_answer_key_pdf,
    store_pdf,
)
from app.exams.schemas import (
    VALID_OPTION_LABELS,
    CropRegionInput,
    CropUpdateRequest,
    CropUpdateResponse,
    ExamAdminOut,
    ExamCreate,
    ExamStatus,
    ExamStudentOut,
    ExamUpdate,
    ExamWithQuestionsAdmin,
    OptionLabel,
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


_ALLOWED_UPLOAD_MIME_TYPES = {
    "",
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
    "image/png",
    "image/jpeg",
    "image/jpg",
}
_FLEXIBLE_KEY_ENTRY = re.compile(
    r"(?:^|[\s,;])(?:Q(?:uestion)?\s*)?(\d{1,4})\s*(?:[.):\-]|\s)\s*([A-Da-d])\b",
    re.IGNORECASE,
)


def _sanitize_filename(raw_name: str | None) -> str:
    base = Path(raw_name or "uploaded.pdf").name
    cleaned = re.sub(r"[\x00-\x1f/\\]+", "_", base).strip(" .")
    return (cleaned or "uploaded.pdf")[:255]


def _parse_pdf_answer_key(answer_key_text: str) -> dict[int, tuple[str, Decimal]]:
    key: dict[int, tuple[str, Decimal]] = {}
    text = answer_key_text.strip()
    if not text:
        return key
    compact = re.sub(r"\s+", "", text)
    if compact and re.fullmatch(r"[A-Da-d]+", compact):
        return {i: (letter.upper(), Decimal(1)) for i, letter in enumerate(compact, 1)}

    comma_tokens = [tok.strip() for tok in text.split(",") if tok.strip()]
    if len(comma_tokens) > 1 and all(re.fullmatch(r"[A-Da-d]", tok) for tok in comma_tokens):
        return {i: (tok.upper(), Decimal(1)) for i, tok in enumerate(comma_tokens, 1)}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and all(re.fullmatch(r"[A-Da-d]", line) for line in lines):
        return {i: (line.upper(), Decimal(1)) for i, line in enumerate(lines, 1)}

    for i in range(len(lines) - 2):
        if (
            re.fullmatch(r"\d+", lines[i])
            and re.fullmatch(r"[A-Da-d]", lines[i + 1])
            and re.fullmatch(r"\d+", lines[i + 2])
        ):
            key[int(lines[i])] = (lines[i + 1].upper(), Decimal(lines[i + 2]))

    for line in text.splitlines():
        row = ANSWER_KEY_ROW.fullmatch(line)
        matched_line = False
        for match in ANSWER_KEY_ENTRY.finditer(line):
            if match.group(2).upper() in "ABCD":
                matched_line = True
                key[int(match.group(1))] = (
                    match.group(2).upper(),
                    Decimal(row.group(3)) if row and row.group(3) else Decimal(1),
                )
        if not matched_line:
            for match in _FLEXIBLE_KEY_ENTRY.finditer(line):
                key[int(match.group(1))] = (match.group(2).upper(), Decimal(1))
    return key


def _process_pdf_upload_sync(
    data: bytes,
) -> tuple[list, int, list[tuple[float, float]], bool, bool, bytes, str | None]:
    doc = open_question_upload(data)
    ocr_warning: str | None = None
    try:
        scan_mode = not any(page.get_text("words") for page in doc)
        detected = detect_scan_questions(doc) if scan_mode else detect_pdf_questions(doc)
        ocr_used = not scan_mode and not detected
        if ocr_used:
            try:
                detected = detect_questions_with_ocr(doc)
            except OCRUnavailable:
                detected = []
                ocr_used = False
                ocr_warning = (
                    "Automatic question detection could not run OCR on this document. "
                    "Draw question crops manually on the rendered pages."
                )
        page_count = len(doc)
        page_dimensions = [(float(page.rect.width), float(page.rect.height)) for page in doc]
        pdf_bytes = doc.tobytes() if not data.startswith(b"%PDF-") else data
    finally:
        doc.close()
    return detected, page_count, page_dimensions, ocr_used, scan_mode, pdf_bytes, ocr_warning


@admin_router.post("/{exam_id}/import-pdf", response_model=ParseQuestionsResponse)
async def import_pdf_route(
    exam_id: UUID,
    file: UploadFile = File(...),
    answer_key_text: str = Form(default=""),
    answer_file: UploadFile | None = File(default=None),
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ParseQuestionsResponse:
    service.require_admin_user_id(identity)
    settings = get_settings()
    exam = db.get(exam_models.Exam, exam_id)
    if exam is None or exam.status != "DRAFT":
        raise HTTPException(status_code=404, detail="Draft examination not found")
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in _ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Upload a PDF, PNG, or JPEG file.")
    data = await file.read(settings.MAX_PDF_BYTES + 1)
    # Version crop reuse, hashing original bytes so raster re-uploads also deduplicate.
    digest = hashlib.sha256(b"graphics-crops-v2\0" + data).hexdigest()
    try:
        (
            detected,
            page_count,
            page_dimensions,
            ocr_used,
            scan_mode,
            data,
            ocr_warning,
        ) = await asyncio.wait_for(
            run_in_threadpool(_process_pdf_upload_sync, data),
            timeout=settings.PDF_PROCESS_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="PDF processing timed out.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    answer_data: bytes | None = None
    if answer_file is not None:
        ans_mime = (answer_file.content_type or "").split(";", 1)[0].strip().lower()
        if ans_mime not in _ALLOWED_UPLOAD_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Answer key file must be a PDF.")
        answer_data = await answer_file.read(settings.MAX_PDF_BYTES + 1)
        try:
            answer_doc = validate_pdf(answer_data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            answer_key_text = "\n".join(
                str(page.get_text("text")) for page in cast(Iterable[Any], answer_doc)
            )
        finally:
            answer_doc.close()
        if not answer_key_text.strip():
            raise HTTPException(status_code=422, detail="Answer PDF contains no selectable text")
    existing = db.scalars(
        select(exam_models.ExamSourceFile)
        .where(exam_models.ExamSourceFile.exam_id == exam_id)
        .where(exam_models.ExamSourceFile.sha256 == digest)
        .order_by(exam_models.ExamSourceFile.uploaded_at.desc())
    ).first()
    if existing is None:
        source_id = uuid4()
        try:
            await run_in_threadpool(store_pdf, source_id, data, detected)
        except OSError as exc:
            raise HTTPException(status_code=500, detail="PDF storage is unavailable") from exc
        db.add(exam_models.ExamSourceFile(
            id=source_id,
            exam_id=exam_id,
            original_filename=_sanitize_filename(file.filename),
            sha256=digest,
            page_count=page_count,
            page_dimensions=json.dumps(page_dimensions),
        ))
        try:
            db.commit()
        except Exception:
            db.rollback()
            delete_source_dir(source_id)
            raise
    else:
        source_id = existing.id
        if existing.page_dimensions is None:
            existing.page_dimensions = json.dumps(page_dimensions)
            db.commit()
        if not source_dir(source_id).is_dir():
            try:
                await run_in_threadpool(store_pdf, source_id, data, detected)
            except OSError as exc:
                raise HTTPException(status_code=500, detail="PDF storage is unavailable") from exc
    key = _parse_pdf_answer_key(answer_key_text)
    mismatch = bool(answer_key_text.strip()) and bool(detected) and (
        len(key) != len(detected) or set(key) != {question.number for question in detected}
    )
    if answer_data is not None and not mismatch:
        try:
            store_answer_key_pdf(source_id, answer_data)
        except OSError as exc:
            raise HTTPException(
                status_code=500, detail="Answer PDF storage is unavailable"
            ) from exc
    items: list[ParsedQuestion] = []
    for question in detected:
        answer = key.get(question.number)
        warnings = list(question.warnings)
        if answer is None:
            warnings.append("No answer in the key; select one before saving.")
        try:
            regions = load_regions(source_id, question.number)
        except (OSError, ValueError):
            regions = [
                {"page": region.page, "bbox": list(region.bbox)} for region in question.regions
            ]
        repaired = has_reviewed_crop(source_id, question.number, regions)
        if repaired:
            warnings = [warning for warning in warnings if not warning.startswith("Crop failed:")]
        items.append(
            ParsedQuestion(
                position=question.number,
                question_text=question.extracted_text or f"Question {question.number}",
                extracted_text=question.extracted_text or None,
                source_file_id=source_id,
                source_number=question.number,
                region_status="needs-review" if warnings else "detected",
                image_urls=[
                    f"/api/admin/exams/{exam_id}/source-images/{source_id}/{question.number}/{i}"
                    for i in range(len(regions))
                ],
                image_regions=regions,
                options=[
                    ParsedOption(label=letter, option_text=f"Option {letter} (see image)")
                    for letter in VALID_OPTION_LABELS
                ],
                answer_label=cast(OptionLabel, answer[0]) if answer else None,
                points=answer[1] if answer else Decimal(1),
                valid=answer is not None and not mismatch and (question.crop_valid or repaired),
                errors=[w for w in warnings if w.startswith("Crop failed:")],
                warnings=warnings,
                pdf_options_text=question.options_text,
                pdf_confidence=(
                    Decimal("0.50")
                    if ocr_used or scan_mode
                    else Decimal("1.00")
                    if len(question.options_text) == 4
                    else Decimal("0.75")
                ),
            )
        )
    extra_errors: list[ParseQuestionsError] = []
    if not detected:
        extra_errors.append(
            ParseQuestionsError(
                block_index=0,
                message=ocr_warning
                or (
                    "No questions were auto-detected. "
                    "Use the page viewer to draw question crops manually."
                ),
            )
        )
    if mismatch:
        extra_errors.append(
            ParseQuestionsError(
                block_index=0,
                message=(
                    f"Answer key has {len(key)} answers but {len(detected)} "
                    "questions were detected"
                ),
            )
        )
    return ParseQuestionsResponse(
        valid_questions=[q for q in items if q.valid],
        invalid_questions=[q for q in items if not q.valid],
        total_blocks=len(items),
        valid_count=sum(q.valid for q in items),
        errors=[
            ParseQuestionsError(block_index=item.position, message=message)
            for item in items for message in item.errors
        ]
        + extra_errors,
        error_count=sum(len(item.errors) for item in items) + len(extra_errors),
        normalized_answer_key=", ".join(f"{n}. {v[0]}" for n, v in sorted(key.items())),
        source_file_id=source_id,
        page_count=page_count,
        page_dimensions=page_dimensions,
        ocr_used=ocr_used,
        scan_mode=scan_mode,
    )


@admin_router.get("/{exam_id}/sources/{source_id}/pages/{page_number}")
def admin_source_page_route(
    exam_id: UUID,
    source_id: UUID,
    page_number: int,
    dpi: int = Query(default=150, ge=72, le=300),
    identity: AuthIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BinaryResponse:
    service.require_admin_user_id(identity)
    source = db.get(exam_models.ExamSourceFile, source_id)
    if source is not None and source.exam_id != exam_id:
        source = None
    if source is None:
        raise HTTPException(status_code=404, detail="Source PDF not found")
    try:
        image = render_source_page(source.id, page_number, dpi=dpi)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Page image not found") from exc
    return BinaryResponse(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "no-store, private"},
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
    return BinaryResponse(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "no-store, private"},
    )


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
            [region.model_dump(exclude_none=True) for region in payload.regions],
            dpi=payload.dpi,
            padding=payload.padding,
            strict=payload.strict,
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
        regions=[CropRegionInput.model_validate(r) for r in regions],
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
router.include_router(recrop_router)
router.include_router(admin_router)
router.include_router(student_router)
