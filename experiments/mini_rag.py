import numpy as np
from dotenv import load_dotenv
from litellm import completion, embedding

load_dotenv()

CHUNKS = [
    {"id": 1, "source": "Blades in the Dark, p.42, Combat > Harm",
     "text": "Harm is recorded in three levels: lesser, moderate, and severe. "
             "Severe harm needs long-term recovery."},
    {"id": 2, "source": "House Rules, p.2",
     "text": "House rule: our table adds a fourth harm level called 'grievous', "
             "which requires a full session of downtime."},
    {"id": 3, "source": "Session 2025-03-14, turn 88",
     "text": "GM: Peter, you're up. PETER: I cast Eldritch Blast at the guard."},
    {"id": 4, "source": "Blades in the Dark, p.47, Combat > Harm",
     "text": "Harm is recorded at two levels - small and big"},
]

SYSTEM = '''Answer using ONLY the numbered sources below. Cite every factual
claim with its bracket number, e.g. [2]. If the sources do not contain the
answer, reply exactly: "I couldn't find that in your materials."
Do not use general knowledge about tabletop games -- the user's house rules
may contradict published rules, and the sources are authoritative.
If sources conflict, present both and note the conflict.'''

SYSTEM_PERMISSIVE = '''Answer first using the numbered sources below.  Cite every factual
claim with its bracket number, e.g. [2]. If the sources do not contain the
answer, use general knowledge of board games. Cite with [GENERAL KNOWLEDGE] if that happens.'''


EMBEDDING_MODEL = "openai/text-embedding-3-small"
#EMBEDDING_MODEL = "voyage/voyage-3-lite"
COMPLETION_MODEL = "openai/gpt-4o-mini"
COMPLETION_MODEL = "anthropic/claude-sonnet-4-5"

def embed(texts):
    r = embedding(model=EMBEDDING_MODEL, input=texts)
    return [np.array(d["embedding"]) for d in r.data]

def cosine(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

# --- Ingest: embed every chunk once ---
print("START")
print(COMPLETION_MODEL)
print(EMBEDDING_MODEL)

vectors = embed([c["text"] for c in CHUNKS])

# --- Query ---
question = "How many levels of harm are there?"
#question = "What is the price of a longsword?"
qvec = embed([question])[0]

scored = [(cosine(qvec, vec), chunk) for chunk, vec in zip(CHUNKS, vectors)]
scored.sort(key=lambda pair: -pair[0])
top = [chunk for _, chunk in scored[:3]]

context = "\n\n".join(
    f'[{i+1}] ({c["source"]})\n{c["text"]}' for i, c in enumerate(top)
)

answer = completion(
    model=COMPLETION_MODEL,
    temperature=0.1,
    messages=[
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"{context}\n\nQuestion: {question}"},
    ],
).choices[0].message.content

print("RETRIEVED:")
for i, c in enumerate(top):
    print(f"  [{i+1}] {c['source']}")
print()
print("ANSWER:")
print(answer)

answer = completion(
    model=COMPLETION_MODEL,
    temperature=0.1,
    messages=[
        {"role": "system", "content": SYSTEM_PERMISSIVE},
        {"role": "user", "content": f"{context}\n\nQuestion: {question}"},
    ],
).choices[0].message.content

print("RETRIEVED:")
for i, c in enumerate(top):
    print(f"  [{i+1}] {c['source']}")
print()
print("ANSWER (Permissive):")
print(answer)