"""Score an extraction against the hand-written facts.

    python app/tools/check_extraction.py "data/Reincarnated as the Unlovable Villainess.pdf"
"""
import sys
from pathlib import Path

from app.ingestion.extract import extract_first_try, extract_pages
from tests.extraction_facts import FACTS, WINDOW


def flatten(text: str) -> str:
    return " ".join(text.split())


def survives(haystack: str, fragments: list[str], window: int) -> bool:
    """True if every fragment appears inside one `window`-sized slice."""
    first = fragments[0]
    start = haystack.find(first)
    while start != -1:
        slice_ = haystack[max(0, start - window):start + window]
        if all(f in slice_ for f in fragments[1:]):
            return True
        start = haystack.find(first, start + 1)
    return False


def main(path: Path):
    pages = {p.number: flatten(p.markdown) for p in extract_first_try(path)}
    passed = 0
    for label, page_no, fragments in FACTS:
        ok = survives(pages.get(page_no, ""), fragments, WINDOW)
        passed += ok
        print(f"  {'PASS' if ok else 'FAIL'}  p{page_no}  {label}")
    print(f"\n{passed}/{len(FACTS)} facts survived extraction")
    return 0 if passed == len(FACTS) else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))