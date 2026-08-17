import numpy as np
from dotenv import load_dotenv
from litellm import embedding

load_dotenv()

# Anthropic has no embedding model of its own, so this compares candidate
# providers. 
MODELS = [
    "openai/text-embedding-3-small",
    "voyage/voyage-3-lite",
    # "cohere/embed-english-v3.0",
]

def embed(texts: list[str], model: str) -> list[list[float]]:
    resp = embedding(model=model, input=texts)
    return [d["embedding"] for d in resp.data]

def cosine(a, b) -> float:
    a, b = np.array(a), np.array(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

# --- Block 1: meaning beats wording ---
texts = [
    "Harm is recorded in three levels: lesser, moderate, and severe.",
    "How badly can a character get hurt in this game?",
    "The tavern keeper offers a room for two silver pieces.",
]

# --- Block 2: the proper-noun weakness ---
names = [
    "Peter cast Eldritch Blast at the guard.",
    "Michael cast Eldritch Blast at the guard.",
    "Peter drank a potion and climbed the wall.",
    "Peter drank health potion",
    "Peter drank mana potion"
]

for model in MODELS:
    print(f"=== {model} ===")

    v = embed(texts, model)
    print("len(vector) =", len(v[0]))
    print("first 5 numbers:", v[0][:5])
    print()
    print("injury rule  <-> injury question :", round(cosine(v[0], v[1]), 3))
    print("injury rule  <-> tavern sentence :", round(cosine(v[0], v[2]), 3))

    n = embed(names, model)
    print()
    print("Peter/Michael, same action :", round(cosine(n[0], n[1]), 3))
    print("Peter, different action    :", round(cosine(n[0], n[2]), 3))
    print("Peter, different potions    :", round(cosine(n[3], n[4]), 3))
    print("First number is close to 1 - you cannot tell whether it was Pater or Michael. ")
    print("Same goes for 3rd number - potions")
    print("Second number is much closer to 0 - it is easy to distinguish one action from the other")
    print()