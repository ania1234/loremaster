"""Print the block geometry of a PDF, sorted by left edge.

    python app/tools/geometry.py "data/Reincarnated as the Unlovable Villainess.pdf" 0
    python app/tools/geometry.py "data/Reincarnated as the Unlovable Villainess.pdf" all
    python app/tools/geometry.py "data/Undisturbed.pdf" all
"""
import sys
from pathlib import Path

import pymupdf


def dump(page):
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    print(f"--- page {page.number + 1}  ({page.rect.width:.0f} x "
          f"{page.rect.height:.0f} pt, {len(blocks)} text blocks)")
    for x0, y0, x1, y1, text, _no, _type in sorted(blocks, key=lambda b: (round(b[0]), b[1])):
        flat = " ".join(text.split())[:52]
        print(f"  x0={x0:6.1f}  x1={x1:6.1f}  w={x1 - x0:5.1f}  "
              f"y0={y0:6.1f}  | {flat}")


if __name__ == "__main__":
    path = Path(sys.argv[1])
    which = sys.argv[2] if len(sys.argv) > 2 else "0"
    doc = pymupdf.open(path)
    pages = range(doc.page_count) if which == "all" else [int(which)]
    for i in pages:
        dump(doc[i])
    doc.close()