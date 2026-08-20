from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pymupdf4llm


@dataclass
class Page:
    number: int          # 1-based
    markdown: str


def is_scanned(path: Path, min_chars_per_page: int = 100) -> bool:
    """Design doc section 6, step 0: sample pages, not just the first one.
    Art-heavy pages in a real text PDF can be sparse too."""
    doc = pymupdf.open(path)
    n = doc.page_count
    sample_idx = sorted({0, n // 2, n - 1, *range(0, n, max(1, n // 8))})
    lengths = [len(doc[i].get_text().strip()) for i in sample_idx if i < n]
    doc.close()
    if not lengths:
        return True
    return (sum(lengths) / len(lengths)) < min_chars_per_page


def extract_pages(path: Path) -> list[Page]:
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
    print(pages[0].markdown[:2000])