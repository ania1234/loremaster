import re
from dataclasses import dataclass, field

from app.config import settings
from app.ingestion.extract import Page
from app.ingestion.tokens import count_tokens

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")

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

def _is_table(paragraph: str) -> bool:
    """A markdown pipe table: every non-blank line starts with '|'."""
    lines = [ln for ln in paragraph.splitlines() if ln.strip()]
    return bool(lines) and all(ln.lstrip().startswith("|") for ln in lines)

def _split_paragraphs(text: str, max_tok: int, overlap_tok: int) -> list[str]:
    """Split text on blank lines, then greedily pack paragraphs into
    overlapping chunks of roughly max_tok tokens, never splitting a
    paragraph or a table across chunks."""
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_tok = 0

    for para in paragraphs:
        para_tok = count_tokens(para)

        if current and current_tok + para_tok > max_tok:
            chunks.append("\n\n".join(current))

            # start the next chunk with trailing paragraphs from this one,
            # kept whole, that add up to roughly overlap_tok tokens; a table
            # is never duplicated into the overlap, however big it is
            carry: list[str] = []
            carry_tok = 0
            for p in reversed(current):
                if _is_table(p):
                    break
                p_tok = count_tokens(p)
                if carry and carry_tok + p_tok > overlap_tok:
                    break
                carry.insert(0, p)
                carry_tok += p_tok
            current, current_tok = carry, carry_tok

        current.append(para)
        current_tok += para_tok

    if current:
        chunks.append("\n\n".join(current))

    return chunks

def chunk_transcript(pages: list[Page]) -> list[Chunk]:
    # For learning purposes, the transcript is split on each dialogue line so
    # every chunk is at most 3 lines (prev, main, next). This gives reciprocal
    # rank fusion something to actually fuse over (otherwise there were only 3
    # chunks, and the LLM inferred correctly from those 3).

    # Flatten every non-blank line, remembering the page it came from.
    lines: list[str] = []
    for page in pages:
        for ln in page.markdown.splitlines():
            if ln.strip():
                lines.append(ln.strip())

    if not lines:
        return []

    chunk_title = lines[0]
    chunks: list[Chunk] = []
    for i in range(len(lines)):
        lo, hi = max(0, i - 1), min(len(lines), i + 2)
        content = "\n\n".join(lines[lo:hi])
        chunks.append(Chunk(
            content=content,
            heading_path=chunk_title,
            page_from=i,
            page_to=i,
            ordinal=i,
            token_count=count_tokens(content),
        ))
    return chunks


def chunk_document(pages: list[Page], doc_type : str) -> list[Chunk]:

    if doc_type == "transcript":
        return chunk_transcript(pages)

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