import json

from litellm import completion
from pydantic import BaseModel, ValidationError

from app.config import settings

PROMPT = """Score each passage 0-10 for how well it helps answer the question.
10 = directly answers it. 0 = unrelated.
Return ONLY a JSON object: {"scores": [{"i": 0, "s": 7}, ...]}
Include every passage index exactly once.

Question: {question}

Passages:
{passages}"""


class Score(BaseModel):
    i: int
    s: int


class Scores(BaseModel):
    scores: list[Score]


def rerank(question: str, candidates: list[dict], top_n: int | None = None,
           max_retries: int = 2) -> list[dict]:
    top_n = top_n or settings.retrieve_final
    if len(candidates) <= top_n:
        return candidates

    passages = "\n\n".join(
        f"[{i}] {c['content'][:600]}" for i, c in enumerate(candidates)
    )
    prompt = PROMPT.format(question=question, passages=passages)

    for _ in range(max_retries):
        raw = completion(
            model=settings.utility_model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        ).choices[0].message.content
        try:
            parsed = Scores.model_validate(json.loads(raw))
            break
        except (json.JSONDecodeError, ValidationError):
            continue
    else:
        # model never complied -- fall back to fusion order rather than failing
        return candidates[:top_n]

    lookup = {s.i: s.s for s in parsed.scores}
    ranked = sorted(
        enumerate(candidates), key=lambda pair: -lookup.get(pair[0], 0)
    )
    out = []
    for idx, cand in ranked[:top_n]:
        row = dict(cand)
        row["rerank_score"] = lookup.get(idx, 0)
        out.append(row)
    return out