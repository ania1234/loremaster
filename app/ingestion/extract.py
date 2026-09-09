from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pymupdf4llm

from app.ingestion.columns import detect_columns, is_spanning, text_blocks

@dataclass
class Page:
    number: int          # 1-based 
    markdown: str
    column_count: int = 1


def is_scanned(src: Path | bytes, min_chars_per_page: int = 100) -> bool:
    """Design doc section 6, step 0: sample pages, not just the first one.
    Art-heavy pages in a real text PDF can be sparse too."""
    if isinstance(src, (bytes, bytearray)):
        doc = pymupdf.open(stream=src, filetype="pdf")
    else:
        doc = pymupdf.open(src)
    n = doc.page_count
    sample_idx = sorted({0, n // 2, n - 1, *range(0, n, max(1, n // 8))})
    lengths = [len(doc[i].get_text().strip()) for i in sample_idx if i < n]
    doc.close()
    if not lengths:
        return True
    return (sum(lengths) / len(lengths)) < min_chars_per_page

def _markdown_in(path: Path, page_no: int, clip: pymupdf.Rect | None) -> str:
    """Markdown for one page, optionally cropped to a rectangle.

    A fresh handle per call: set_cropbox mutates the page, and reusing a
    handle would leave later columns cropped to earlier ones.
    """
    doc = pymupdf.open(path)
    try:
        if clip is not None:
            doc[page_no].set_cropbox(clip)
        return pymupdf4llm.to_markdown(doc, pages=[page_no]).strip()
    finally:
        doc.close()

def extract_page(path: Path, page_no: int, doc_type: str) -> Page:
    doc = pymupdf.open(path)
    page = doc[page_no]
    width = page.rect.width
    columns = detect_columns(page)
    banners = [b for b in text_blocks(page) if is_spanning(b, width)]
    top, bottom = page.rect.y0, page.rect.y1
    doc.close()

    if len(columns) <= 1:                       # the common case: leave it alone
        return Page(page_no + 1, _markdown_in(path, page_no, None), 1)

    parts = []
    if banners:
        parts.extend(b[4].strip() for b in sorted(banners, key=lambda b: (b[1], b[0])))
    for col in columns:
        parts.append(_markdown_in(path, page_no,
                                  pymupdf.Rect(col.x0, top, col.x1, bottom)))

    return Page(page_no + 1, "\n\n".join(p for p in parts if p), len(columns))

def extract_pages(path: Path, doc_type: str) -> list[Page]:
    """Same signature as L15 -- everything downstream is unaffected."""
    doc = pymupdf.open(path)
    count = doc.page_count
    doc.close()
    pages = []
    for i in range(count):
        pages.append(extract_page(path, i, doc_type))
        print(f"  extracted {i + 1}/{count} pages")
    return pages

def extract_first_try(path: Path) -> list[Page]:
    """Markdown per page, headings preserved, page numbers retained."""
    raw = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    return [
        Page(number=p["metadata"]["page_number"], markdown=p["text"])
        for p in raw
    ]


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1])
    if is_scanned(path):
        print("REJECTED: this PDF appears to be a scan with no text layer.")
        raise SystemExit(1)

    pages = extract_pages(path)
    print(f"{len(pages)} pages extracted\n")
    print(pages[2].markdown[:5000])