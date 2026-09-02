import re

from litellm import completion

from app.config import settings

SYSTEM = '''Answer using ONLY the numbered sources below. Cite every factual
claim with its bracket number, e.g. [2]. If the sources do not contain the
answer, reply exactly: "I couldn't find that in your materials."

Do not use general knowledge about tabletop games -- the user's house rules
may contradict published rules, and the sources are authoritative.
If sources conflict, present both and note the conflict.
If the sources answer only part of the question, answer that part and state
what is missing.
State the coverage of your answer, e.g. "Based on the Injury chapter
(pp. 41-46)...", so that a partial answer is visibly partial.'''

REFUSAL = "I couldn't find that in your materials."
CITATION = re.compile(r"\[(\d+)\]")


def verify_citations(answer: str, n_sources: int) -> list[int]:
    """Return any cited numbers that do not exist. Design doc s8, mechanism 4."""
    cited = {int(m) for m in CITATION.findall(answer)}
    return sorted(n for n in cited if n < 1 or n > n_sources)


def generate(question: str, context: str, n_sources: int) -> tuple[str, bool]:
    def call() -> str:
        return completion(
            stream=False,
            model=settings.chat_model,
            temperature=settings.temperature,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user",
                 "content": f"{context}\n\nQuestion: {question}"},
            ],
        ).choices[0].message.content

    answer = call()
    bad = verify_citations(answer, n_sources)
    if bad:
        print(f"  hallucinated citation(s) {bad}; regenerating once")
        answer = call()
        bad = verify_citations(answer, n_sources)
        if bad:
            return answer, False      # caller surfaces an "unverified" flag
    return answer, True