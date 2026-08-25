import re
from dataclasses import dataclass, field

from app.config import settings
from app.ingestion.extract import Page
from app.ingestion.tokens import count_tokens

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")

@dataclass
class Chunk:
    content: str
    heading_path: str
    page_from: int
    page_to: int
    ordinal: int = 0
    token_count: int = field(default=0)

def _sections(pages: list[Page]):
    """Walk the document, tracking the current heading stack."""
    stack: list[str] = []
    buf: list[str] = []
    start_page = pages[0].number if pages else 1
    end_page = start_page

    for page in pages:
        for line in page.markdown.splitlines():
            m = HEADING.match(line)
            if m:
                if buf and any(x.strip() for x in buf):
                    yield " > ".join(stack), "\n".join(buf), start_page, end_page
                level, title = len(m.group(1)), m.group(2).strip()
                stack = stack[: level - 1] + [title]
                buf, start_page = [], page.number
            else:
                buf.append(line)
        end_page = page.number

    if buf and any(x.strip() for x in buf):
        yield " > ".join(stack), "\n".join(buf), start_page, end_page

def _split_paragraphs(text: str, max_tok: int, overlap_tok: int) -> list[str]:
    """Split oversized text on blank lines; never break a table."""
    blocks, current, in_table = [], [], False
    for para in text.split("\n\n"):
        is_table = bool(TABLE_ROW.match(para.strip().splitlines()[0])) if para.strip() else False
        if is_table:
            if current:
                blocks.append("\n\n".join(current)); current = []
            blocks.append(para)          # table stays whole, whatever its size
        else:
            current.append(para)
    if current:
        blocks.append("\n\n".join(current))

    out, buf = [], []
    for block in blocks:
        candidate = buf + [block]
        if count_tokens("\n\n".join(candidate)) > max_tok and buf:
            out.append("\n\n".join(buf))
            # carry the tail of the previous chunk forward as overlap
            tail, tail_tokens = [], 0
            for prev in reversed(buf):
                tail_tokens += count_tokens(prev)
                tail.insert(0, prev)
                if tail_tokens >= overlap_tok:
                    break
            buf = tail + [block]
        else:
            buf = candidate
    if buf:
        out.append("\n\n".join(buf))
    return out

def chunk_document(pages: list[Page]) -> list[Chunk]:
    max_tok = settings.chunk_max_tokens
    min_tok = settings.chunk_min_tokens
    overlap = settings.chunk_overlap_tokens

    raw: list[Chunk] = []
    for path, text, p_from, p_to in _sections(pages):
        text = text.strip()
        if not text:
            continue
        pieces = ([text] if count_tokens(text) <= max_tok
                  else _split_paragraphs(text, max_tok, overlap))
        for piece in pieces:
            raw.append(Chunk(piece, path, p_from, p_to,
                             token_count=count_tokens(piece)))

    # merge-forward pass for undersized chunks
    merged: list[Chunk] = []
    carry: Chunk | None = None
    for c in raw:
        if carry:
            c = Chunk(carry.content + "\n\n" + c.content,
                      carry.heading_path or c.heading_path,
                      carry.page_from, c.page_to,
                      token_count=count_tokens(carry.content + c.content))
            carry = None
        if c.token_count < min_tok:
            carry = c
            continue
        merged.append(c)
    if carry:
        if merged:
            last = merged[-1]
            last.content += "\n\n" + carry.content
            last.page_to = carry.page_to
            last.token_count = count_tokens(last.content)
        else:
            merged.append(carry)

    for i, c in enumerate(merged):
        c.ordinal = i
    return merged