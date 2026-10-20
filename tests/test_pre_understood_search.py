import os
import uuid
from contextlib import contextmanager
from datetime import date

import pytest
from dotenv import load_dotenv

from app.retrieval import search
from app.retrieval.understand import (
    Filters,
    StructuredQuery,
    decide_date_range,
    decide_scope,
    decide_type,
    understand,
)

load_dotenv()

# decide_type / decide_scope call the Typesafe JEV API; decide_date_range and the
# fallbacks inside understand() call the utility model through litellm.
needs_jev = pytest.mark.skipif(
    not os.environ.get("TYPESAFE_API_KEY"), reason="needs TYPESAFE_API_KEY")
needs_llm = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="needs OPENAI_API_KEY")


#test if decide_type from understand.py returns the correct type for a given question
@needs_jev
@pytest.mark.parametrize("question, expected", [
    ("How many spell slots does a 5th level wizard have?", "ruleset"),
])
def test_decide_type(question, expected):
    assert decide_type(question) == expected


#test if decide_scope from understand.py returns the correct scope for a given question
@needs_jev
@pytest.mark.parametrize("question, expected", [
    ("List every NPC the party has met so far.", "broad"),
])
def test_decide_scope(question, expected):
    assert decide_scope(question) == expected


#test if decide_date_range from understand.py returns the correct date range for a given question
@needs_llm
@pytest.mark.parametrize("question, expected", [
    ("What happened in the session on 12 March 2025?",
     {"from": date(2025, 3, 12), "to": date(2025, 3, 12)}),
])
def test_decide_date_range(question, expected):
    assert decide_date_range(question) == expected


#test if understand from understand.py returns the correct StructuredQuery for a given question and previous questions
@needs_jev
@needs_llm
@pytest.mark.parametrize("question, previous_questions, expected", [
    # "he" and the session date only make sense with the earlier question.
    ("Did he cast fireball?",
     ["What did Peter do in the session on 12 March 2025?"],
     StructuredQuery(
         search_text="Did he cast fireball?",
         filters=Filters(doc_type="transcript",
                         session_date_from=date(2025, 3, 12),
                         session_date_to=date(2025, 3, 12)),
         scope="narrow",
     )),
])
def test_understand(question, previous_questions, expected):
    result = understand(question, previous_questions)
    assert result.filters == expected.filters
    assert result.scope == expected.scope
    assert "fireball" in result.search_text.lower()


#test if hybrid_search_pre_understood from search.py returns the correct results for a given user_id, query, and conversation_id
class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    def execute(self, stmt, params):
        self.params = params
        return _FakeResult(self.rows)


@pytest.mark.parametrize("query, history_rows", [
    ("Did he cast fireball?",
     [{"content": "Who is Peter?"},
      {"content": "What did Peter do in the session on 12 March 2025?"}]),
])
def test_hybrid_search_pre_understood(monkeypatch, query, history_rows):
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    session = _FakeSession(history_rows)
    understood = StructuredQuery(search_text=query)
    fused = [{"id": uuid.uuid4(), "content": "Peter hurls a fireball at the goblins."}]
    calls = {}

    @contextmanager
    def fake_session_for_user(uid):
        calls["session_uid"] = uid
        yield session

    def fake_understand(question, previous_questions):
        calls["understand"] = (question, previous_questions)
        return understood

    def fake_hybrid_search(uid, structured_query, limit=None):
        calls["hybrid_search"] = (uid, structured_query, limit)
        return fused

    monkeypatch.setattr(search, "session_for_user", fake_session_for_user)
    monkeypatch.setattr(search, "understand", fake_understand)
    monkeypatch.setattr(search, "hybrid_search", fake_hybrid_search)

    result = search.hybrid_search_pre_understood(
        user_id, query, conversation_id=conversation_id, limit=8)

    assert result == fused
    assert calls["session_uid"] == user_id
    assert session.params["cid"] == str(conversation_id)
    assert session.params["uid"] == str(user_id)
    # Previous questions arrive oldest first and without the current query.
    assert calls["understand"] == (query, [r["content"] for r in history_rows])
    assert calls["hybrid_search"] == (user_id, understood, 8)


#test if hybrid_search drops a doc_type filter that rules out every chunk, instead of returning nothing
def test_hybrid_search_relaxes_doc_type_when_empty(monkeypatch):
    user_id = uuid.uuid4()
    understood = StructuredQuery(search_text="What is the game about?",
                                 filters=Filters(doc_type="transcript"))
    row = {"id": uuid.uuid4(), "content": "A ruleset chunk."}
    seen_doc_types = []

    def fake_search(uid, structured_query, k=None):
        seen_doc_types.append(structured_query.filters.doc_type)
        return [] if structured_query.filters.doc_type else [row]

    monkeypatch.setattr(search, "vector_search", fake_search)
    monkeypatch.setattr(search, "keyword_search", fake_search)

    result = search.hybrid_search(user_id, understood, limit=8)

    assert [r["id"] for r in result] == [row["id"]]
    assert seen_doc_types == ["transcript", "transcript", None, None]
    # The caller's query is left untouched.
    assert understood.filters.doc_type == "transcript"
