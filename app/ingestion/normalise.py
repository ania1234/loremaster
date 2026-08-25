#actually not needed, yet, but might be useful in the future
import re
from collections import Counter

from app.ingestion.extract import Page


def find_repeated_lines(pages: list[Page], threshold: float = 0.6) -> set[str]:
    """Lines appearing on more than `threshold` of pages are headers/footers."""
    counts: Counter[str] = Counter()
    for page in pages:
        # a line can repeat within a page; count it once per page
        seen = {ln.strip() for ln in page.markdown.splitlines() if ln.strip()}
        counts.update(seen)

    cutoff = len(pages) * threshold
    return {line for line, c in counts.items() if c > cutoff and len(line) < 120}


def clean_page(markdown: str, furniture: set[str]) -> str:
    lines = [ln for ln in markdown.splitlines() if ln.strip() not in furniture]
    text = "\n".join(lines)

    text = re.sub(r"[ \t]+", " ", text)          # collapse runs of spaces
    text = re.sub(r"\n{3,}", "\n\n", text)        # at most one blank line
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # rejoin hyphenated line breaks
    return text.strip()


def normalise(pages: list[Page]) -> list[Page]:
    furniture = find_repeated_lines(pages)
    return [Page(p.number, clean_page(p.markdown, furniture)) for p in pages]