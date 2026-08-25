"""Detect the column layout of a PDF page.

The approach is the vertical half of a classic XY-cut: project text onto the
x axis, and read the columns off as runs of ink separated by empty gutters.
"""
from dataclasses import dataclass

import numpy as np
import pymupdf

# --- thresholds, all in PDF points (72 per inch) ------------------------
MIN_GUTTER = 12       # narrower gaps are word spacing or table alignment
MIN_COLUMN = 60       # no real body column is under ~0.8 inch wide
SPAN_RATIO = 0.40     # blocks wider than this fraction of the page span columns
PAD = 4               # widen each column slightly so glyphs are not clipped


@dataclass(frozen=True)
class Column:
    x0: float
    x1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0


def text_blocks(page):
    """Text blocks only, non-empty, as (x0, y0, x1, y1, text) tuples."""
    return [
        (b[0], b[1], b[2], b[3], b[4])
        for b in page.get_text("blocks")
        if b[6] == 0 and b[4].strip()
    ]


def is_spanning(block, page_width: float) -> bool:
    """True for banners, full-width headings, and page-wide rules."""
    return (block[2] - block[0]) > SPAN_RATIO * page_width


def detect_columns(page) -> list[Column]:
    """Column x-ranges, left to right. A single-column page returns one Column."""
    width = int(page.rect.width)
    coverage = np.zeros(width + 2)

    for block in text_blocks(page):
        if is_spanning(block, width):
            continue                      # banners do not vote
        coverage[max(0, int(block[0])):min(width, int(block[2])) + 1] += 1

    # runs of ink
    runs, start = [], None
    for x in range(width + 1):
        if coverage[x] > 0 and start is None:
            start = x
        elif coverage[x] == 0 and start is not None:
            runs.append([start, x - 1])
            start = None
    if start is not None:
        runs.append([start, width])

    # merge across gaps too narrow to be real gutters
    merged: list[list[int]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] < MIN_GUTTER:
            merged[-1][1] = run[1]
        else:
            merged.append(run)

    return [Column(r[0] - PAD, r[1] + PAD) for r in merged
            if r[1] - r[0] >= MIN_COLUMN]