"""Render pages with boxes drawn on, for eyeballing layout.

    python app/tools/overlay.py "data/Reincarnated as the Unlovable Villainess.pdf"
    python app/tools/overlay.py "data/Undisturbed.pdf"
"""
import sys
from pathlib import Path

import pymupdf

from app.ingestion import columns

OUT = Path("debug")


def render(path: Path, dpi: int = 100):
    OUT.mkdir(exist_ok=True)
    doc = pymupdf.open(path)          # fresh handle: draw_rect mutates in memory

    i=0
    for page in doc:
        extracted_columns = columns.detect_columns(page)
        for col in extracted_columns:
            page.draw_rect(pymupdf.Rect(col.x0, 0, col.x1, page.rect.height), color=(0, 1, 0), width=0.8)
        for x0, y0, x1, y1, _text, _no, btype in page.get_text("blocks"):
            if btype==0 and i<1:
                print(f"Block number {_no} with text {_text}")
            colour = (1, 0, 0) if btype == 0 else (0, 0, 1)
            page.draw_rect(pymupdf.Rect(x0, y0, x1, y1), color=colour, width=0.8)
        target = OUT / f"p{page.number + 1:02d}.png"
        page.get_pixmap(dpi=dpi).save(target)
        print(target)
        i += 1
    doc.close()                        # never doc.save() -- the boxes are debug only


if __name__ == "__main__":
    render(Path(sys.argv[1]))