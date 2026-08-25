import tiktoken

from app.ingestion.extract import extract_page

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def truncate_to_tokens(text: str, limit: int) -> str:
    ids = _enc.encode(text)
    return _enc.decode(ids[:limit]) if len(ids) > limit else text


if __name__ == "__main__":
    s = "Harm is recorded in three levels: lesser, moderate, and severe."
    ids = _enc.encode(s)
    print(f"{len(s)} characters -> {len(ids)} tokens")
    print([_enc.decode([i]) for i in ids])
    page = extract_page("data/Reincarnated as the Unlovable Villainess.pdf", 0)
    tokens = count_tokens(page.markdown)
    print(f"{len(page.markdown)} characters -> {tokens} tokens. Ratio: { len(page.markdown)/tokens:.3f} characters per token")
    page = extract_page("data/Reincarnated as the Unlovable Villainess.pdf", 6)
    tokens = count_tokens(page.markdown)
    print(f"MOSTLY TABLE: {len(page.markdown)} characters -> {tokens} tokens. Ratio: { len(page.markdown)/tokens:.3f} characters per token")
