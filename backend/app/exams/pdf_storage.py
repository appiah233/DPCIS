"""Private local storage for imported PDFs and their derived question images."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from uuid import UUID

import fitz

from app.exams.pdf_import import PdfQuestion, render_region, validate_pdf

MIN_CROP_HEIGHT = 30.0
MAX_RENDER_DPI = 300


def storage_root() -> Path:
    default_root = Path(__file__).resolve().parents[2] / "var" / "exam-pdfs"
    root = Path(os.environ.get("EXAM_PDF_STORAGE_DIR", str(default_root))).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def source_dir(source_id: UUID) -> Path:
    return storage_root() / str(source_id)


def store_answer_key_pdf(source_id: UUID, data: bytes) -> None:
    """Keep the admin's original answer key private beside its question PDF."""
    directory = source_dir(source_id)
    if not (directory / "source.pdf").is_file():
        raise FileNotFoundError("Question PDF source is unavailable")
    temporary = directory / "answer-key.pdf.tmp"
    temporary.write_bytes(data)
    temporary.replace(directory / "answer-key.pdf")


def store_pdf(source_id: UUID, data: bytes, questions: list[PdfQuestion]) -> None:
    directory = source_dir(source_id)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "source.pdf").write_bytes(data)
    doc = validate_pdf(data)
    try:
        for question in questions:
            regions = [
                {"page": region.page, "bbox": list(region.bbox)} for region in question.regions
            ]
            (directory / f"{question.number}.json").write_text(
                json.dumps(regions), encoding="utf-8"
            )
            for index, region in enumerate(question.regions):
                (directory / f"{question.number}-{index}.png").write_bytes(
                    render_region(doc, region)
                )
    finally:
        doc.close()


def load_regions(source_id: UUID, question_number: int) -> list[dict]:
    return json.loads(
        (source_dir(source_id) / f"{question_number}.json").read_text(encoding="utf-8")
    )


def load_image(source_id: UUID, question_number: int, index: int) -> bytes:
    if question_number < 1 or index < 0 or index >= len(load_regions(source_id, question_number)):
        raise FileNotFoundError
    return (source_dir(source_id) / f"{question_number}-{index}.png").read_bytes()


def regenerate_crops(
    source_id: UUID,
    question_number: int,
    regions: list[dict] | None = None,
    *,
    dpi: int = 200,
    padding: float = 0.0,
) -> list[dict]:
    """Validate and re-render a question from its stored original PDF.

    The stored bbox is the canonical crop. Padding expands it only for render;
    unchanged settings produce byte-identical PNGs with PyMuPDF's deterministic
    rasterizer. All images are rendered before replacing existing files.
    """
    if not 72 <= dpi <= MAX_RENDER_DPI:
        raise ValueError("DPI must be between 72 and 300")
    if not math.isfinite(padding) or not 0 <= padding <= 30:
        raise ValueError("Padding must be between 0 and 30 points")
    if question_number < 1:
        raise ValueError("Question number must be positive")
    directory = source_dir(source_id)
    source = directory / "source.pdf"
    if not source.is_file():
        raise FileNotFoundError("Stored PDF not found")
    selected = regions if regions is not None else load_regions(source_id, question_number)
    if not selected:
        raise ValueError("At least one page region is required")
    doc = validate_pdf(source.read_bytes())
    try:
        previous_page = 0
        images: list[bytes] = []
        normalized: list[dict] = []
        for region in selected:
            page_number = region.get("page")
            bbox = region.get("bbox")
            if not isinstance(page_number, int) or not 1 <= page_number <= len(doc):
                raise ValueError("Crop page is outside the PDF")
            if page_number <= previous_page:
                raise ValueError("Page regions must be in increasing page order")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                raise ValueError("Crop bbox needs four coordinates")
            try:
                x0, y0, x1, y1 = (float(value) for value in bbox)
            except (TypeError, ValueError) as exc:
                raise ValueError("Crop bbox coordinates must be numbers") from exc
            page = doc[page_number - 1]
            if (
                not all(math.isfinite(v) for v in (x0, y0, x1, y1))
                or x0 < 0
                or y0 < 0
                or x1 > page.rect.width
                or y1 > page.rect.height
                or x1 <= x0
                or y1 - y0 < MIN_CROP_HEIGHT
            ):
                raise ValueError("Crop bbox must lie inside the page and be at least 30 pt tall")
            clip = fitz.Rect(
                max(0, x0 - padding),
                max(0, y0 - padding),
                min(page.rect.width, x1 + padding),
                min(page.rect.height, y1 + padding),
            )
            images.append(page.get_pixmap(clip=clip, dpi=dpi, alpha=False).tobytes("png"))
            normalized.append({"page": page_number, "bbox": [x0, y0, x1, y1]})
            previous_page = page_number
    finally:
        doc.close()
    for index, image in enumerate(images):
        temporary = directory / f"{question_number}-{index}.png.tmp"
        temporary.write_bytes(image)
        temporary.replace(directory / f"{question_number}-{index}.png")
    (directory / f"{question_number}.json").write_text(json.dumps(normalized), encoding="utf-8")
    return normalized
