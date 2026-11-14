"""Coordinate-based PDF MCQ detection and faithful question crops.

Problem: selectable text loses diagrams and scientific notation. The source PDF
is authoritative for display; text is a secondary search and accessibility aid.
Headers must increase by one, occupy the main left text column, and have nearby
stem text. Repeated text in the same page band is excluded from crop bounds.
Scanning is O(words + pages * candidates); rendering cost tracks crop pixels.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, cast

import fitz

MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_PAGES = 200
RENDER_DPI = 200
PADDING = 8.0


@dataclass(frozen=True)
class PdfRegion:
    page: int  # one-based
    bbox: tuple[float, float, float, float]


@dataclass
class PdfQuestion:
    number: int
    regions: list[PdfRegion] = field(default_factory=list)
    extracted_text: str = ""
    options_text: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    options_kind: str = "text"
    section: str | None = None


class OCRUnavailable(ValueError):
    """OCR could not run because optional software is unavailable."""


def validate_pdf(data: bytes) -> fitz.Document:
    if not data.startswith(b"%PDF-"):
        raise ValueError("The uploaded file is not a PDF.")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("Choose a PDF up to 100 MB.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ValueError("The PDF could not be opened.") from exc
    if doc.is_encrypted:
        doc.close()
        raise ValueError("Encrypted PDFs cannot be imported.")
    if not 1 <= len(doc) <= MAX_PAGES:
        doc.close()
        raise ValueError(f"The PDF must contain 1 to {MAX_PAGES} pages.")
    return doc


def repeated_bands(doc: fitz.Document) -> dict[int, list[tuple[float, float]]]:
    """Identify text repeated at approximately the same y on most pages."""
    occurrences: Counter[tuple[str, int]] = Counter()
    lines_by_page: list[list[tuple[str, float, float]]] = []
    for page in cast(Iterable[fitz.Page], doc):
        lines = []
        page_dict = cast(dict[str, Any], page.get_text("dict"))
        for block in page_dict["blocks"]:
            for line in block.get("lines", []):
                value = " ".join(span["text"].strip() for span in line["spans"]).strip()
                if value:
                    y0, y1 = float(line["bbox"][1]), float(line["bbox"][3])
                    lines.append((value, y0, y1))
        lines_by_page.append(lines)
        occurrences.update({(value.casefold(), round(y0 / 8)) for value, y0, _ in lines})
    threshold = max(2, (len(doc) + 1) // 2)
    return {
        index: [
            (y0 - 2, y1 + 2)
            for value, y0, y1 in lines
            if occurrences[(value.casefold(), round(y0 / 8))] >= threshold
        ]
        for index, lines in enumerate(lines_by_page)
    }


def _excluded(y0: float, y1: float, bands: list[tuple[float, float]]) -> bool:
    return any(y0 >= top and y1 <= bottom for top, bottom in bands)


def _ordered_words(page: fitz.Page) -> list[tuple[Any, ...]]:
    """PDF stream order is not reading order, even within one page."""
    words = cast(list[tuple[Any, ...]], page.get_text("words"))
    return sorted(words, key=lambda w: (w[1], w[0]))


def _graphic_regions(page: fitz.Page) -> list[fitz.Rect]:
    """Coalesce adjacent vector strokes into tables and drawings."""
    pieces = [fitz.Rect(item["rect"]) for item in page.get_drawings()]
    groups: list[fitz.Rect] = []
    for piece in pieces:
        merged = piece
        remaining: list[fitz.Rect] = []
        for group in groups:
            if (group + (-1, -1, 1, 1)).intersects(merged + (-1, -1, 1, 1)):
                merged |= group
            else:
                remaining.append(group)
        groups = remaining + [merged]
    # A later stroke can join two previously separate groups.
    changed = True
    while changed:
        changed = False
        result: list[fitz.Rect] = []
        for group in groups:
            for index, previous in enumerate(result):
                if (previous + (-1, -1, 1, 1)).intersects(group + (-1, -1, 1, 1)):
                    result[index] |= group
                    changed = True
                    break
            else:
                result.append(group)
        groups = result
    return [group for group in groups if group.width >= 25 and group.height >= 18]


def _inside_graphic(word: tuple, regions: list[fitz.Rect]) -> bool:
    centre = fitz.Point((word[0] + word[2]) / 2, (word[1] + word[3]) / 2)
    return any(region.contains(centre) for region in regions)


def detect_pdf_questions(doc: fitz.Document) -> list[PdfQuestion]:
    pages = list(cast(Iterable[fitz.Page], doc))
    bands = repeated_bands(doc)
    graphics = {index: _graphic_regions(page) for index, page in enumerate(pages)}
    headers: list[tuple[int, int, float, int]] = []
    columns_by_page: dict[int, bool] = {}
    expected = 1
    for page_index, page in enumerate(pages):
        words = _ordered_words(page)
        numeric = [
            w
            for w in words
            if re.fullmatch(r"\d{1,3}", w[4])
            and not _excluded(w[1], w[3], bands[page_index])
            and not _inside_graphic(w, graphics[page_index])
        ]
        right_candidates = [
            w for w in numeric if page.rect.width * 0.45 <= w[0] < page.rect.width * 0.7
        ]
        right = min((w[0] for w in right_candidates), default=0)
        # Require two plausible numbered headers in the right column before
        # treating a page as two-column; isolated numeric table cells do not qualify.
        right_header_numbers = {
            int(w[4])
            for w in right_candidates
            if abs(w[0] - right) <= 22
            and any(
                other[0] > w[2]
                and other[0] - w[2] < 35
                and abs(other[1] - w[1]) < 7
                and other[4][0].isalpha()
                for other in words
            )
        }
        two_columns = sum(n >= expected for n in right_header_numbers) >= 2
        columns_by_page[page_index] = two_columns
        for column in (0, 1) if two_columns else (0,):
            candidates = [
                w
                for w in numeric
                if (
                    page.rect.width * 0.45 <= w[0] < page.rect.width * 0.7
                    if column
                    else w[0] < page.rect.width * 0.3
                )
            ]
            for word in sorted(candidates, key=lambda w: w[1]):
                if word[4] != str(expected):
                    continue
                nearby = [
                    w
                    for w in words
                    if w[0] > word[2] and 0 <= w[0] - word[2] < 35 and abs(w[1] - word[1]) < 7
                ]
                if not nearby or nearby[0][4].casefold() in {"and", "only"}:
                    continue
                headers.append((expected, page_index, float(word[1]), column))
                expected += 1
    questions: list[PdfQuestion] = []
    for index, (number, start_page, start_y, start_column) in enumerate(headers):
        next_page, next_y, next_column = (
            (headers[index + 1][1], headers[index + 1][2], headers[index + 1][3])
            if index + 1 < len(headers)
            else (len(doc), 0.0, 0)
        )
        question = PdfQuestion(number=number)
        option_labels: list[tuple[int, tuple]] = []
        for word in _ordered_words(doc[start_page]):
            if word[1] >= start_y:
                break
            if word[4].casefold() == "paper":
                same_line = [
                    other for other in _ordered_words(doc[start_page])
                    if other[0] > word[2] and abs(other[1] - word[1]) < 5
                ]
                if same_line and same_line[0][4].isdigit():
                    question.section = f"Paper {same_line[0][4]}"
        if question.section is None and questions:
            question.section = questions[-1].section
        text_parts: list[str] = []
        for page_index in range(start_page, min(next_page + 1, len(doc))):
            page = doc[page_index]
            if page_index > start_page and (
                not question.regions
                or question.regions[-1].bbox[3] < doc[page_index - 1].rect.height - 80
            ):
                break
            if page_index == next_page and next_y <= 0:
                break
            column = start_column if page_index == start_page else 0
            x0, x1 = (
                ((page.rect.width / 2, page.rect.width) if column else (0, page.rect.width / 2))
                if columns_by_page.get(page_index)
                else (0, page.rect.width)
            )
            words = [
                w
                for w in _ordered_words(page)
                if x0 <= w[0]
                and w[2] <= x1
                and w[1] >= 20
                and not _excluded(w[1], w[3], bands[page_index])
            ]
            top = max(0.0, start_y - PADDING) if page_index == start_page else 25.0
            bottom_limit = (
                next_y - PADDING
                if page_index == next_page and column == next_column
                else page.rect.height
            )
            selected = [w for w in words if w[1] >= top and w[3] <= bottom_limit]
            if not selected:
                continue
            drawings = [
                drawing["rect"]
                for drawing in page.get_drawings()
                if drawing["rect"].y0 >= top
                and drawing["rect"].y0 < bottom_limit
                and drawing["rect"].x0 >= x0
                and drawing["rect"].x1 <= x1
            ]
            bottom = min(
                bottom_limit,
                max([w[3] for w in selected] + [rect.y1 for rect in drawings]) + PADDING,
            )
            # Use the full page width: PDF text/drawing runs can disappear when
            # their underlying stream crosses a narrow horizontal clip.
            rect = (float(x0), top, float(x1), bottom)
            question.regions.append(PdfRegion(page_index + 1, rect))
            text_parts.extend(
                w[4] for w in sorted(selected, key=lambda w: (round(w[1] / 3), w[0]))
            )
            line_groups: dict[tuple[int, int], list[tuple]] = {}
            for word in selected:
                line_groups.setdefault((word[5], word[6]), []).append(word)
            for line_words in line_groups.values():
                ordered = sorted(line_words, key=lambda w: w[0])
                for word_index, word in enumerate(ordered):
                    label = word[4].strip(".()")
                    if label not in {"A", "B", "C", "D"}:
                        continue
                    option_labels.append((page_index, word))
                    if _inside_graphic(word, graphics[page_index]):
                        continue
                    following = []
                    for next_word in ordered[word_index + 1 :]:
                        if next_word[4].strip(".()") in {"A", "B", "C", "D"}:
                            break
                        following.append(next_word[4])
                    question.options_text.setdefault(label, " ".join(following))
        graphic_labels = [
            (page_index, word, region)
            for page_index, word in option_labels
            for region in graphics[page_index]
            if _inside_graphic(word, [region])
        ]
        if graphic_labels:
            question.options_kind = (
                "image" if any(region.width > 250 for _, _, region in graphic_labels) else "table"
            )
        elif option_labels:
            if any(
                sum(
                    region.width > 40
                    and region.height > 35
                    and 0 <= region.y0 - word[1] < 55
                    for region in graphics[page_index]
                ) >= 4
                for page_index, word in option_labels
            ):
                question.options_kind = "image"
            else:
                line_labels: dict[tuple[int, int], set[str]] = {}
                for page_index, word in option_labels:
                    line_labels.setdefault((page_index, round(word[1] / 4)), set()).add(word[4])
                if any(len(labels) >= 2 for labels in line_labels.values()):
                    question.options_kind = "inline_row"
        question.extracted_text = " ".join(text_parts)
        if not question.options_text:
            question.warnings.append("No option letters detected; review the crop.")
        if any(region.bbox[3] - region.bbox[1] < 45 for region in question.regions):
            question.warnings.append("Short crop; review the boundary.")
        if any(region.bbox[3] - region.bbox[1] > 650 for region in question.regions):
            question.warnings.append("Tall crop; review the boundary.")
        questions.append(question)
    return questions


def render_region(doc: fitz.Document, region: PdfRegion) -> bytes:
    page = doc[region.page - 1]
    return page.get_pixmap(clip=fitz.Rect(region.bbox), dpi=RENDER_DPI, alpha=False).tobytes("png")


def detect_questions_with_ocr(doc: fitz.Document) -> list[PdfQuestion]:
    """Build a temporary coordinate text layer from Tesseract over source pages."""
    try:
        import pytesseract  # type: ignore[import-not-found]
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as exc:
        raise OCRUnavailable(
            "OCR is needed for this PDF. Install optional pytesseract and Pillow plus Tesseract."
        ) from exc
    searchable = fitz.open()
    try:
        for source_page in doc:
            page = searchable.new_page(width=source_page.rect.width, height=source_page.rect.height)
            pix = source_page.get_pixmap(dpi=200, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            try:
                data = pytesseract.image_to_data(
                    image, output_type=pytesseract.Output.DICT, config="--psm 6"
                )
            except pytesseract.TesseractNotFoundError as exc:
                raise OCRUnavailable(
                    "OCR is needed for this PDF, but the Tesseract executable is not installed."
                ) from exc
            except RuntimeError as exc:
                raise OCRUnavailable(
                    "OCR could not process this PDF; review the scan quality."
                ) from exc
            scale_x = source_page.rect.width / pix.width
            scale_y = source_page.rect.height / pix.height
            for index, raw in enumerate(data["text"]):
                word = raw.strip()
                if not word or float(data["conf"][index]) < 20:
                    continue
                x = float(data["left"][index]) * scale_x
                y = float(data["top"][index]) * scale_y
                height = float(data["height"][index]) * scale_y
                page.insert_text((x, y + height), word, fontsize=max(5, min(height, 16)))
        questions = detect_pdf_questions(searchable)
        for question in questions:
            question.warnings.append("OCR used; review text and crop boundaries carefully.")
        return questions
    finally:
        searchable.close()
