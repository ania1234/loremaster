import sys
import uuid

from app.generation.answer import generate
from app.generation.context import build_context
from app.retrieval.search import vector_search

DEV_USER = uuid.UUID("00000000-0000-0000-0000-000000000000")


def main() -> None:
    question = " ".join(sys.argv[1:])
    if not question:
        print('usage: python scripts/ask.py "your question"')
        raise SystemExit(1)

    candidates = vector_search(DEV_USER, question, k=8)
    context, used = build_context(candidates)
    answer, verified = generate(question, context, len(used))

    print(answer)
    print("\n--- sources ---")
    for i, c in enumerate(used, 1):
        print(f"[{i}] {c['title']} p.{c['page_from']} :: {c['heading_path']}")
    if not verified:
        print("\n!! UNVERIFIED: the answer cited a source that does not exist.")


if __name__ == "__main__":
    main()