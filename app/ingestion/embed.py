import time

from litellm import embedding

from app.config import settings
from app.ingestion.chunk import Chunk

BATCH = 100


def contextualise(chunk: Chunk, session_date: str | None = None) -> str:
    """Design doc section 6, step 4: prepend structure BEFORE embedding."""
    if session_date:
        return f"[Session: {session_date}] {chunk.content}"
    if chunk.heading_path:
        return f"{chunk.heading_path} -- {chunk.content}"
    return chunk.content


def embed_texts(texts: list[str], max_retries: int = 5) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i : i + BATCH]
        for attempt in range(max_retries):
            try:
                resp = embedding(model=settings.embedding_model, input=batch)
                out.extend(d["embedding"] for d in resp.data)
                break
            except Exception as exc:  # rate limits, transient network errors
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"embed_texts: giving up after {max_retries} attempts "
                        f"on batch {i}-{i + len(batch)} of {len(texts)} "
                        f"(model={settings.embedding_model!r}): {exc}"
                    ) from exc
                wait = 2 ** attempt
                print(f"  embed retry {attempt + 1} in {wait}s ({exc})")
                time.sleep(wait)
        print(f"  embedded {min(i + BATCH, len(texts))}/{len(texts)}")
    return out


def embed_chunks(chunks: list[Chunk], session_date: str | None = None):
    return embed_texts([contextualise(c, session_date) for c in chunks])