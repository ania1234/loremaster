import uuid

from sqlalchemy import text

from app.config import settings
from app.db.models import SessionLocal
from app.ingestion.embed import embed_texts
from app.retrieval.fuse import reciprocal_rank_fusion

VECTOR_SQL = text("""
    SELECT c.id, c.document_id, c.content, c.heading_path,
           c.page_from, c.page_to, c.ordinal,
           d.title, 1 - (c.embedding <=> (:qvec)::vector) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.user_id = :uid
    ORDER BY c.embedding <=> (:qvec)::vector
    LIMIT :k
""")

KEYWORD_SQL = text("""
    SELECT c.id, c.document_id, c.content, c.heading_path,
           c.page_from, c.page_to, c.ordinal, d.title,
           ts_rank_cd(c.tsv, websearch_to_tsquery('english', :q)) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.user_id = :uid
      AND c.tsv @@ websearch_to_tsquery('english', :q)
    ORDER BY score DESC
    LIMIT :k
""")


def keyword_search(user_id: uuid.UUID, query: str, k: int | None = None):
    k = k or settings.retrieve_candidates
    with SessionLocal() as session:
        rows = session.execute(
            KEYWORD_SQL, {"q": query, "uid": str(user_id), "k": k}
        ).mappings().all()
    return [dict(r) for r in rows]


def vector_search(user_id: uuid.UUID, query: str, k: int | None = None):
    """user_id is the first argument, always. Design doc section 5, layer 1."""
    k = k or settings.retrieve_candidates
    qvec = embed_texts([query])[0]
    with SessionLocal() as session:
        rows = session.execute(
            VECTOR_SQL, {"qvec": str(qvec), "uid": str(user_id), "k": k}
        ).mappings().all()
    return [dict(r) for r in rows]

def hybrid_search(user_id: uuid.UUID, query: str, limit: int | None = None):
    limit = limit or settings.retrieve_candidates
    vec = vector_search(user_id, query, k=limit)
    kw = keyword_search(user_id, query, k=limit)
    return reciprocal_rank_fusion([vec, kw], limit=limit)

if __name__ == "__main__":
    import uuid
    user_id = "00000000-0000-0000-0000-000000000000"
    question = "what should I eat for breakfast"
    search_result = vector_search(uuid.UUID(user_id), question, 8)
    for row in search_result:
        print(row['content'][:200])
    print("KEYWORD SEARCH")
    search_result = keyword_search(uuid.UUID(user_id), question, 8)
    for row in search_result:
        print(row['content'][:200])
    print("HYBRID SEARCH")
    search_result = hybrid_search(uuid.UUID(user_id), question, 8)
    for row in search_result:
        print(row['content'][:200])
