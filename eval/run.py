import uuid

import yaml
from litellm import completion

from app.config import settings
from app.generation.answer import REFUSAL, generate
from app.generation.context import build_context
from app.retrieval.rerank import rerank
from app.retrieval.search import hybrid_search

DEV_USER = uuid.UUID("00000000-0000-0000-0000-000000000000")

JUDGE = """You are grading an answer for GROUNDEDNESS only.
Is every factual claim in the ANSWER supported by the SOURCES?
Reply with exactly one word: GROUNDED or UNGROUNDED.

SOURCES:
{context}

ANSWER:
{answer}"""


def judge_grounded(context: str, answer: str) -> bool:
    verdict = completion(
        model=settings.utility_model,
        temperature=0.0,
        messages=[{"role": "user",
                   "content": JUDGE.format(context=context, answer=answer)}],
    ).choices[0].message.content
    return "UNGROUNDED" not in verdict.upper()


def main() -> None:
    questions = yaml.safe_load(open("eval/questions.yaml"))
    recalls, grounded, refusal_ok = [], [], []

    for q in questions:
        candidates = hybrid_search(DEV_USER, q["question"])
        top = rerank(q["question"], candidates)
        retrieved = {str(c["id"]) for c in top}

        expected = set(q.get("expected_chunk_ids") or [])
        if expected:
            recalls.append(len(expected & retrieved) / len(expected))

        context, used = build_context(top)
        answer, _ = generate(q["question"], context, len(used))

        refused = REFUSAL.lower() in answer.lower()
        refusal_ok.append(refused == q["should_refuse"])
        if not q["should_refuse"]:
            grounded.append(judge_grounded(context, answer))

        flag = "ok " if refused == q["should_refuse"] else "MISS"
        print(f"{flag} {q['id']:>4} [{q['kind']:<17}] {q['question'][:50]}")

    def pct(xs):
        return f"{100 * sum(xs) / len(xs):.1f}%" if xs else "n/a"

    print("\n=== results ===")
    print(f"recall@{settings.retrieve_final:<3}    {pct(recalls)}")
    print(f"groundedness    {pct(grounded)}")
    print(f"refusal acc.    {pct(refusal_ok)}")


if __name__ == "__main__":
    main()