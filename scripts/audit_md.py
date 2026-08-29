"""Run the PDF pipeline, unchanged, against a Markdown file.

Nothing here is production code. It exists to make four failure modes
visible in one screen of output.
"""
from pathlib import Path

from app.ingestion.extract import Page, is_scanned, extract_pages
from app.ingestion.normalise import normalise, find_repeated_lines
from app.ingestion.chunk import chunk_document

path = Path("data/sesja.md")
raw = path.read_text(encoding="utf-8")
print(f"raw          {len(raw):>6} chars  {len(raw.splitlines()):>4} lines")

# 1 -- the scan check
try:
    print(f"is_scanned   {is_scanned(path)}")
except Exception as e:
    print(f"is_scanned   raised {type(e).__name__}: {e}")

# 2 -- the extractor
try:
    print(f"extract      {len(extract_pages(path))} pages")
except Exception as e:
    print(f"extract      raised {type(e).__name__}: {e}")

# 3 -- normalisation
pages = extract_pages(path)
furniture = find_repeated_lines(pages)
cleaned = normalise(pages)
print(f"furniture    {len(furniture)} lines classified as headers/footers")
print(f"normalised   {len(cleaned[0].markdown):>6} chars   "
      f"({100 * len(cleaned[0].markdown) / len(raw):.0f}% of the original)")

# 4 -- chunking, WITHOUT normalisation, so stage 3 can't hide stage 4
chunks = chunk_document(pages)
print(f"\nchunks {len(chunks)}")
for c in chunks:
    print("NEW CHUNK")
    print(c.content)