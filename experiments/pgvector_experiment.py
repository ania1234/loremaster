import os

import psycopg
from dotenv import load_dotenv
from litellm import embedding
from pgvector.psycopg import register_vector

load_dotenv()
# psycopg wants a plain URL, without the SQLAlchemy "+psycopg" part
DSN = os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")

def embed(texts):
    r = embedding(model="openai/text-embedding-3-small", input=texts)
    return [d["embedding"] for d in r.data]

SENTENCES = [
    "Harm is recorded in three levels: lesser, moderate, and severe.",
    "A successful Prowl roll lets you move unseen past a single guard.",
    "The crew's heat rises when a score attracts official attention.",
]

with psycopg.connect(DSN) as conn:
    register_vector(conn)

    # --- store ---
    vecs = embed(SENTENCES)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE demo_chunks;")
        for text, vec in zip(SENTENCES, vecs):
            cur.execute(
                "INSERT INTO demo_chunks (content, embedding) VALUES (%s, %s)",
                (text, vec),
            )
    conn.commit()

    # --- search ---
    question = "What are the effects of a roll?"
    qvec = embed([question])[0]
    with conn.cursor() as cur:
        cur.execute(
            """SELECT content, 1 - (embedding <=> %s::vector) AS similarity
               FROM demo_chunks
               ORDER BY embedding <=> %s::vector
               LIMIT 3""",
            (qvec, qvec),
        )
        print(f"Q: {question}\n")
        for content, sim in cur.fetchall():
            print(f"{sim:.3f}  {content}")