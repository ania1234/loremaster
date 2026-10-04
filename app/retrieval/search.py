import uuid

from sqlalchemy import text

from app.config import settings
from app.db.session import session_for_user
from app.ingestion.embed import embed_texts
from app.retrieval.fuse import reciprocal_rank_fusion
from app.retrieval.understand import Filters, StructuredQuery, understand

VECTOR_SQL = """
    SELECT c.id, c.document_id, c.content, c.heading_path,
           c.page_from, c.page_to, c.ordinal,
           d.title, 1 - (c.embedding <=> (:qvec)::vector) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.user_id = :uid
      {filters}
    ORDER BY c.embedding <=> (:qvec)::vector
    LIMIT :k
"""

KEYWORD_SQL = """
    SELECT c.id, c.document_id, c.content, c.heading_path,
           c.page_from, c.page_to, c.ordinal, d.title,
           ts_rank_cd(c.tsv, websearch_to_tsquery('english', :q)) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.user_id = :uid
      AND c.tsv @@ websearch_to_tsquery('english', :q)
      {filters}
    ORDER BY score DESC
    LIMIT :k
"""

# OFFSET 1 drops the newest user message: chat.py stores the current question
# before retrieval runs, so it would otherwise count as its own history.
PREVIOUS_QUESTIONS_SQL = """
    SELECT content FROM (
        SELECT m.content, m.created_at
        FROM messages m
        JOIN conversations conv ON conv.id = m.conversation_id
        WHERE m.conversation_id = :cid
          AND conv.user_id = :uid
          AND m.role = 'user'
        ORDER BY m.created_at DESC
        LIMIT :n OFFSET 1
    ) prev
    ORDER BY created_at
"""


def _filter_clauses(filters: Filters) -> tuple[str, dict]:
    """Turn the understood filters into WHERE fragments + their bind params.

    Only the filters the model actually set are spliced in, so an unfiltered
    query produces exactly the SQL we had before.
    """
    clauses: list[str] = []
    params: dict = {}

    if filters.doc_type:
        clauses.append("AND d.doc_type = :doc_type")
        params["doc_type"] = filters.doc_type
    if filters.document_ids:
        clauses.append("AND c.document_id = ANY((:document_ids)::uuid[])")
        params["document_ids"] = [str(d) for d in filters.document_ids]
    if filters.session_date_from:
        clauses.append("AND d.session_date >= :session_date_from")
        params["session_date_from"] = filters.session_date_from
    if filters.session_date_to:
        clauses.append("AND d.session_date <= :session_date_to")
        params["session_date_to"] = filters.session_date_to

    return "\n      ".join(clauses), params


def _candidate_k(structured_query: StructuredQuery, k: int | None) -> int:
    """How many candidates to pull for this query.

    Broad questions -- "list all...", "summarise..." -- need the full pool;
    narrow ones do fine on fewer. An explicit positive k wins; anything else
    (None, 0, a negative) falls back to the scope default. The result is never
    below 1: a search that can only return nothing is never what we want.
    """
    if k is not None and k > 0:
        return k
    default = (settings.retrieve_candidates_narrow
               if structured_query.scope == "narrow"
               else settings.retrieve_candidates)
    return max(1, default)


def _build(sql: str, filters: Filters, base_params: dict):
    filter_sql, filter_params = _filter_clauses(filters)
    return text(sql.format(filters=filter_sql)), {**base_params, **filter_params}


def keyword_search(user_id: uuid.UUID, structured_query: StructuredQuery,
                   k: int | None = None):
    k = _candidate_k(structured_query, k)
    stmt, params = _build(
        KEYWORD_SQL,
        structured_query.filters,
        {"q": structured_query.search_text, "uid": str(user_id), "k": k},
    )
    with session_for_user(user_id) as session:
        rows = session.execute(stmt, params).mappings().all()
    return [dict(r) for r in rows]


def vector_search(user_id: uuid.UUID, structured_query: StructuredQuery,
                  k: int | None = None):
    """user_id is the first argument, always. Design doc section 5, layer 1."""
    k = _candidate_k(structured_query, k)
    qvec = embed_texts([structured_query.search_text])[0]
    stmt, params = _build(
        VECTOR_SQL,
        structured_query.filters,
        {"qvec": str(qvec), "uid": str(user_id), "k": k},
    )
    with session_for_user(user_id) as session:
        rows = session.execute(stmt, params).mappings().all()
    return [dict(r) for r in rows]

def hybrid_search_pre_understood(user_id: uuid.UUID, query: str, conversation_id: uuid.UUID | None = None, limit: int | None = None):
    #fetch previous questions from the conversation.
    # Watch out - the current query is there as well and should be omitted.
    # Sort the questions chronologically, the oldest first.
    rows = []
    if conversation_id is not None:
        with session_for_user(user_id) as session:
            rows = session.execute(
                text(PREVIOUS_QUESTIONS_SQL),
                {"cid": str(conversation_id), "uid": str(user_id),
                 "n": settings.previous_questions_limit},
            ).mappings().all()
    previous_questions = [r['content'] for r in rows]
    #understand the query
    structured_query = understand(query, previous_questions)
    return hybrid_search(user_id, structured_query, limit=limit)

def hybrid_search(user_id: uuid.UUID, structured_query: StructuredQuery,
                  limit: int | None = None):
    limit = _candidate_k(structured_query, limit)
    vec = vector_search(user_id, structured_query, k=limit)
    kw = keyword_search(user_id, structured_query, k=limit)
    return reciprocal_rank_fusion([vec, kw], limit=limit)

if __name__ == "__main__":
    import uuid
    user_id = "8779b84a-93d0-4891-bd09-33dde423dcb6"
    question = "Is Peter a warlock"
    structured_query = StructuredQuery(search_text=question)
    search_result = vector_search(uuid.UUID(user_id), structured_query, 8)
    for row in search_result:
        print(row['content'][:200])
    print("KEYWORD SEARCH")
    search_result = keyword_search(uuid.UUID(user_id), structured_query, 8)
    for row in search_result:
        print(row['content'][:200])
    print("HYBRID SEARCH")
    search_result = hybrid_search(uuid.UUID(user_id), structured_query, 8)
    for row in search_result:
        print(row['content'][:200])
