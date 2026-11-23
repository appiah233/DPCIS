"""Private local storage for imported PDFs and their derived question images."""

from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path
from uuid import UUID, uuid4

import fitz

from app.config import get_settings
from app.exams.pdf_import import (
    PdfQuestion,
    graphic_boxes,
    render_region,
    repeated_bands,
    validate_pdf,
    white_crop_border,
)

MIN_CROP_HEIGHT = 30.0
MAX_RENDER_DPI = 300


def storage_root() -> Path:
    default_root = Path(__file__).resolve().parents[2] / "var" / "exam-pdfs"
    configured = os.environ.get("EXAM_PDF_STORAGE_DIR") or get_settings().EXAM_PDF_STORAGE_DIR
    root = Path(configured or str(default_root)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def source_dir(source_id: UUID) -> Path:
    return storage_root() / str(source_id)


def delete_source_dir(source_id: UUID) -> None:
    """Safely remove stored PDF and rendered images for an abandoned or deleted source."""
    directory = source_dir(source_id)
    if directory.exists():
        shutil.rmtree(directory, ignore_errors=True)


def _normalize_bbox(
    bbox: list[float] | tuple[float, ...], width: float, height: float
) -> list[float]:
    if width <= 0 or height <= 0:
        return [0.0, 0.0, 1.0, 1.0]
    x0, y0, x1, y1 = (float(v) for v in bbox)
    return [
        round(max(0.0, min(1.0, x0 / width)), 6),
        round(max(0.0, min(1.0, y0 / height)), 6),
        round(max(0.0, min(1.0, x1 / width)), 6),
        round(max(0.0, min(1.0, y1 / height)), 6),
    ]


def _resolve_bbox_points(
    region: dict, width: float, height: float
) -> tuple[float, float, float, float]:
    bbox = region.get("bbox")
    bbox_norm = region.get("bbox_normalized")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return tuple(float(v) for v in bbox)  # type: ignore[return-value]
    if isinstance(bbox_norm, (list, tuple)) and len(bbox_norm) == 4:
        nx0, ny0, nx1, ny1 = (float(v) for v in bbox_norm)
        return (nx0 * width, ny0 * height, nx1 * width, ny1 * height)
    raise ValueError("Crop bbox needs four coordinates")


def store_answer_key_pdf(source_id: UUID, data: bytes) -> None:
    """Keep the admin's original answer key private beside its question PDF."""
    directory = source_dir(source_id)
    if not (directory / "source.pdf").is_file():
        raise FileNotFoundError("Question PDF source is unavailable")
    temporary = directory / "answer-key.pdf.tmp"
    try:
        temporary.write_bytes(data)
        temporary.replace(directory / "answer-key.pdf")
    finally:
        temporary.unlink(missing_ok=True)


def store_pdf(source_id: UUID, data: bytes, questions: list[PdfQuestion]) -> None:
    directory = source_dir(source_id)
    directory.mkdir(parents=True, exist_ok=False)
    try:
        (directory / "source.pdf").write_bytes(data)
        doc = validate_pdf(data)
        try:
            for question in questions:
                regions = []
                for region in question.regions:
                    page = doc[region.page - 1]
                    bbox = list(region.bbox)
                    regions.append({
                        "page": region.page,
                        "bbox": bbox,
                        "bbox_normalized": _normalize_bbox(bbox, page.rect.width, page.rect.height),
                    })
                (directory / f"{question.number}.json").write_text(
                    json.dumps(regions), encoding="utf-8"
                )
                for index, region in enumerate(question.regions):
                    (directory / f"{question.number}-{index}.png").write_bytes(
                        render_region(doc, region)
                    )
        finally:
            doc.close()
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def load_regions(source_id: UUID, question_number: int) -> list[dict]:
    if question_number < 1:
        raise FileNotFoundError
    return json.loads(
        (source_dir(source_id) / f"{question_number}.json").read_text(encoding="utf-8")
    )


def load_image(source_id: UUID, question_number: int, index: int) -> bytes:
    if question_number < 1 or index < 0 or index >= len(load_regions(source_id, question_number)):
        raise FileNotFoundError
    return (source_dir(source_id) / f"{question_number}-{index}.png").read_bytes()


def has_reviewed_crop(source_id: UUID, question_number: int, regions: list[dict]) -> bool:
    """Trust a successful administrator repair only for the exact stored regions."""
    directory = source_dir(source_id)
    try:
        reviewed = json.loads(
            (directory / f"{question_number}.reviewed.json").read_text(encoding="utf-8")
        )
        return bool(regions) and reviewed == regions and all(
            (directory / f"{question_number}-{index}.png").is_file()
            for index in range(len(regions))
        )
    except (OSError, ValueError):
        return False


def render_source_page(source_id: UUID, page_number: int, *, dpi: int = 150) -> bytes:
    """Render and cache a full PDF page as a lossless PNG for visual crop review."""
    max_dpi = get_settings().MAX_PDF_RENDER_DPI
    if not 72 <= dpi <= max_dpi:
        raise ValueError(f"DPI must be between 72 and {max_dpi}")
    if page_number < 1:
        raise FileNotFoundError("Page number must be positive")
    directory = source_dir(source_id)
    source = directory / "source.pdf"
    if not source.is_file():
        raise FileNotFoundError("Stored PDF not found")
    cached = directory / f"page-{page_number}-{dpi}.png"
    if cached.is_file():
        return cached.read_bytes()
    doc = validate_pdf(source.read_bytes())
    try:
        if page_number > len(doc):
            raise FileNotFoundError("Page number outside PDF")
        page = doc[page_number - 1]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        png_bytes = pix.tobytes("png")
    finally:
        doc.close()
    temporary = directory / f"page-{page_number}-{dpi}.{uuid4().hex}.png.tmp"
    try:
        temporary.write_bytes(png_bytes)
        try:
            temporary.replace(cached)
        except PermissionError:
            if not cached.is_file():
                raise
    finally:
        temporary.unlink(missing_ok=True)
    return png_bytes


def regenerate_crops(
    source_id: UUID,
    question_number: int,
    regions: list[dict] | None = None,
    *,
    dpi: int = 220,
    padding: float = 0.0,
    strict: bool = True,
) -> list[dict]:
    """Validate and re-render a question from its stored original PDF.

    The stored bbox is the canonical crop. Padding expands it only for render;
    unchanged settings produce byte-identical PNGs with PyMuPDF's deterministic
    rasterizer. All images are rendered before replacing existing files.
    """
    max_dpi = get_settings().MAX_PDF_RENDER_DPI
    if not 72 <= dpi <= max_dpi:
        raise ValueError(f"DPI must be between 72 and {max_dpi}")
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
        bands = repeated_bands(doc) if strict else []
        previous_page = 0
        images: list[bytes] = []
        normalized: list[dict] = []
        for region in selected:
            page_number = region.get("page")
            if not isinstance(page_number, int) or not 1 <= page_number <= len(doc):
                raise ValueError("Crop page is outside the PDF")
            if page_number < previous_page:
                raise ValueError("Page regions must be in nondecreasing page order")
            page = doc[page_number - 1]
            try:
                x0, y0, x1, y1 = _resolve_bbox_points(region, page.rect.width, page.rect.height)
            except (TypeError, ValueError) as exc:
                raise ValueError("Crop bbox coordinates must be numbers") from exc
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
            if strict and any(
                box.intersects(clip) and not clip.contains(box)
                for box in graphic_boxes(page, bands[page_number - 1])
            ):
                raise ValueError("Crop failed: partially clipped graphic; expand the crop.")
            pix = page.get_pixmap(clip=clip, dpi=dpi, alpha=False)
            if strict and not white_crop_border(pix):
                raise ValueError(
                    "Crop failed: non-white pixels touch the left/right "
                    "or top or bottom 2px border."
                )
            images.append(pix.tobytes("png"))
            normalized.append({
                "page": page_number,
                "bbox": [x0, y0, x1, y1],
                "bbox_normalized": _normalize_bbox(
                    [x0, y0, x1, y1], page.rect.width, page.rect.height
                ),
            })
            previous_page = page_number
    finally:
        doc.close()
    for index, image in enumerate(images):
        temporary = directory / f"{question_number}-{index}.png.tmp"
        try:
            temporary.write_bytes(image)
            temporary.replace(directory / f"{question_number}-{index}.png")
        finally:
            temporary.unlink(missing_ok=True)
    json_tmp = directory / f"{question_number}.json.tmp"
    try:
        json_tmp.write_text(json.dumps(normalized), encoding="utf-8")
        json_tmp.replace(directory / f"{question_number}.json")
    finally:
        json_tmp.unlink(missing_ok=True)
    reviewed = directory / f"{question_number}.reviewed.json"
    reviewed_tmp = directory / f"{question_number}.{uuid4().hex}.reviewed.tmp"
    try:
        reviewed_tmp.write_text(json.dumps(normalized), encoding="utf-8")
        reviewed_tmp.replace(reviewed)
    finally:
        reviewed_tmp.unlink(missing_ok=True)
    return normalized
