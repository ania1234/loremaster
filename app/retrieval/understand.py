import json
import uuid
from datetime import date
from typing import Literal

from litellm import completion
from pydantic import BaseModel, ValidationError

from app.config import settings

PROMPT = """Convert the user's question into a structured search query.

Today's date is {today}.

The user's documents:
{documents}

Return ONLY JSON of this shape:
{{
  "search_text": "the words worth searching for, proper nouns kept",
  "filters": {{
    "doc_type": "ruleset" | "transcript" | null,
    "document_ids": ["uuid", ...],
    "session_date_from": "YYYY-MM-DD" | null,
    "session_date_to": "YYYY-MM-DD" | null
  }},
  "scope": "narrow" | "broad"
}}

"scope" is "broad" when the question asks for a complete list, an overview,
or every instance of something ("what are all the...", "list the...",
"summarise..."). Otherwise it is "narrow".

Question: {question}"""


class Filters(BaseModel):
    doc_type: Literal["ruleset", "transcript"] | None = None
    document_ids: list[uuid.UUID] = []
    session_date_from: date | None = None
    session_date_to: date | None = None


class StructuredQuery(BaseModel):
    search_text: str
    filters: Filters = Filters()
    scope: Literal["narrow", "broad"] = "narrow"


def understand(question: str, documents: list[dict],
               max_retries: int = 2) -> StructuredQuery:
    doc_lines = "\n".join(
        f'- {d["id"]} | "{d["title"]}" | {d["doc_type"]}'
        f'{" | session " + str(d["session_date"]) if d.get("session_date") else ""}'
        for d in documents
    ) or "(none)"

    prompt = PROMPT.format(today=date.today().isoformat(),
                           documents=doc_lines, question=question)

    for _ in range(max_retries):
        raw = completion(
            model=settings.utility_model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        ).choices[0].message.content
        try:
            return StructuredQuery.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError):
            continue

    # Never fail the user's question because the parser misbehaved.
    return StructuredQuery(search_text=question)