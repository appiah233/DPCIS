"""Regenerate small deterministic PDF layout fixtures for Phase 2 tests."""

from pathlib import Path

import fitz

HERE = Path(__file__).parent


def add_question(page: fitz.Page, number: int, x: int, y: int) -> None:
    page.insert_text((x, y), str(number), fontsize=12)
    page.insert_text((x + 22, y), f"Question {number} has one answer.", fontsize=12)
    for offset, label in enumerate("ABCD", start=1):
        page.insert_text((x + 22, y + offset * 20), f"{label} Option {label}", fontsize=11)


def main() -> None:
    two = fitz.open()
    page = two.new_page(width=600, height=800)
    add_question(page, 1, 40, 100)
    add_question(page, 2, 40, 300)
    add_question(page, 3, 330, 100)
    add_question(page, 4, 330, 300)
    two.save(HERE / "two_column.pdf")
    two.close()

    span = fitz.open()
    first = span.new_page(width=600, height=800)
    first.insert_text((40, 620), "1", fontsize=12)
    first.insert_text((62, 620), "Question one continues on the next page.", fontsize=12)
    for y in (680, 720, 760, 785):
        first.insert_text((62, y), f"Continuation at {y}.", fontsize=11)
    second = span.new_page(width=600, height=800)
    second.insert_text((62, 60), "A Option A", fontsize=11)
    second.insert_text((62, 80), "B Option B", fontsize=11)
    add_question(second, 2, 40, 300)
    span.save(HERE / "spanning_pages.pdf")
    span.close()

    source = fitz.open()
    scan_page = source.new_page(width=600, height=800)
    add_question(scan_page, 1, 40, 100)
    add_question(scan_page, 2, 40, 300)
    png = scan_page.get_pixmap(dpi=150, alpha=False).tobytes("png")
    source.close()
    scanned = fitz.open()
    page = scanned.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=png)
    scanned.save(HERE / "scanned_image_only.pdf")
    scanned.close()


if __name__ == "__main__":
    main()
