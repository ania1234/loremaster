"""Find vertical whitespace bands by projecting text onto the x axis."""
"""python app/tools/gutters.py "data/Reincarnated as the Unlovable Villainess.pdf" --per-page """
import sys
from pathlib import Path

import numpy as np
import pymupdf

MIN_GUTTER = 10          # points; narrower than this is just word spacing


def zero_runs(coverage, min_width):
    """Return (start, end) for each run of zeros at least min_width wide."""
    runs, start = [], None
    for x, value in enumerate(coverage):
        if value == 0 and start is None:
            start = x
        elif value != 0 and start is not None:
            if x - start >= min_width:
                runs.append((start, x - 1))
            start = None
    if start is not None and len(coverage) - start >= min_width:
        runs.append((start, len(coverage) - 1))
    return runs


def coverage_for(pages, width):
    cov = np.zeros(width + 2)
    for page in pages:
        for word in page.get_text("words"):
            x0, x1 = int(word[0]), int(word[2])
            cov[max(0, x0):min(width, x1) + 1] += 1
    return cov


if __name__ == "__main__":
    doc = pymupdf.open(Path(sys.argv[1]))
    width = int(doc[0].rect.width)

    if "--whole-document" in sys.argv:
        cov = coverage_for(list(doc), width)
        print("pooled:", zero_runs(cov, MIN_GUTTER))
    else:
        for page in doc:
            cov = coverage_for([page], width)
            print(f"page {page.number + 1}: {zero_runs(cov, MIN_GUTTER)}")
    doc.close()