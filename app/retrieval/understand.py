import json
import os
import re
import uuid
from datetime import date
from typing import Literal

import httpx
from litellm import completion
from pydantic import BaseModel, ValidationError
from sqlalchemy import case

from app.config import settings

PROMPT = """Convert the user's question into a structured search query.

Today's date is {today}.

Return ONLY JSON of this shape:
{{
  "search_text": "the words worth searching for, proper nouns kept",
  "filters": {{
    "doc_type": "ruleset" | "transcript" | null,
    "session_date_from": "YYYY-MM-DD" | null,
    "session_date_to": "YYYY-MM-DD" | null
  }},
  "scope": "narrow" | "broad"
}}

"scope" is "broad" when the question asks for a complete list, an overview,
or every instance of something ("what are all the...", "list the...",
"summarise..."). Otherwise it is "narrow".

Question: {question}"""

PROMPT_JEV_DECIDE_TYPE = """Decide whether the user's question is about a ruleset or a transcript.
 The question is: {question}"""

PROMPT_LLM_DECIDE_TYPE = """Decide whether the user's question is about a ruleset or a transcript.
Ruleset questions ask about the rules of the game, and are usually about the future.
Transcript questions ask about the past, and are usually about the behaviour of the players.
Return only "ruleset" or "transcript" or "unknown", with no other text.
The question is: {question}"""

PROMPT_JEV_DECIDE_SCOPE = """Decide whether the user's question is broad or narrow.
Broad questions ask for a complete list, an overview, or every instance of something.
The question is: {question}"""

PROMPT_JEV_DECIDE_DATE = """Decide whether the user's question is about a specific date or date range.
The question is: {question}"""

PROMPT_LLM_DECIDE_DATE = """Today's date is {today}. Decide whether the user's question is about a specific date or date range.
The question is a part of ongoing conversation with a bot.
The previous questions were: {previous_questions}
Return only a JSON object with "from" and "to" keys as "YYYY-MM-DD" strings. Use null for a key that is not mentioned, and {{"from": null, "to": null}} if no specific date or date range is mentioned.
Sometimes the date can be inferred from the previous questions, so consider them when deciding as well.
Sometimes you can infer the date from today's date by doing simple operations, eg. if today is 01.09, and the question is "What happened last week?", you can infer that the date range is 25.08 - 31.08.
NEVER return your reasoning, only a final JSON object. If you are unsure, return null for both keys.
The question is: {question}"""

PROMPT_DECIDE_KEYWORDS = """Decide which keywords are worth searching for in the user's question.
The question is a part of ongoing conversation with a bot.
The previous questions were: {previous_questions}
Return only the list of words, with proper nouns kept, and no other text.
The question is: {question}
"""


class Filters(BaseModel):
    doc_type: Literal["ruleset", "transcript"] | None = None
    session_date_from: date | None = None
    session_date_to: date | None = None


class StructuredQuery(BaseModel):
    search_text: str
    filters: Filters = Filters()
    scope: Literal["narrow", "broad"] = "narrow"

JEV_MIN_CONFIDENCE = 0.6


def decide_type(question: str) -> Literal["ruleset", "transcript", "unknown"]:
    try:
        response = httpx.post(
            f"{settings.typesafe_api_base}/v1/systemone",
            headers={"Authorization": f"Bearer {os.environ.get("TYPESAFE_API_KEY")}"},
            json={
                "state": question,
                "model": settings.jev_model,
                "questions": {
                    "doc_type": {
                        "type": "choice",
                        "instructions": PROMPT_JEV_DECIDE_TYPE.format(question=question),
                        "criteria": {
                            "ruleset": "The game itself: its premise, setting, rules, how mechanics work, what players can do",
                            "transcript": "What happened in past sessions, what the players did",
                        },
                    }
                },
            },
            timeout=10.0,
        )
        response.raise_for_status()
        answer = response.json()["answers"]["doc_type"]
    except (httpx.HTTPError, KeyError, ValueError):
        return "unknown"

    if answer.get("confidence", 0.0) < JEV_MIN_CONFIDENCE:
        return "unknown"
    return answer["choice"]

def decide_scope(question: str) -> Literal["narrow", "broad", "unknown"]:
    try:
        response = httpx.post(
            f"{settings.typesafe_api_base}/v1/systemone",
            headers={"Authorization": f"Bearer {os.environ.get("TYPESAFE_API_KEY")}"},
            json={
                "state": question,
                "model": settings.jev_model,
                "questions": {
                    "scope": {
                        "type": "choice",
                        "instructions": PROMPT_JEV_DECIDE_SCOPE.format(question=question),
                        "criteria": {
                            "narrow": "The question is about a specific aspect of the game or a particular session",
                            "broad": "The question is about the game in general or multiple sessions",
                        },
                    }
                },
            },
            timeout=10.0,
        )
        response.raise_for_status()
        answer = response.json()["answers"]["scope"]
    except (httpx.HTTPError, KeyError, ValueError):
        return "unknown"

    if answer.get("confidence", 0.0) < JEV_MIN_CONFIDENCE:
        return "unknown"
    return answer["choice"]

def decide_type_expensive(question: str) -> Literal["ruleset", "transcript", "unknown"]:
    """Fallback to a more expensive LLM call if the JEV model is uncertain."""
    try:
        response = completion(
            model=settings.utility_model,
            temperature=0.0,
            messages=[{"role": "user", "content": PROMPT_LLM_DECIDE_TYPE.format(question=question)}],
        )
        answer = response.choices[0].message.content.strip().lower()
    except Exception:
        return "unknown"

    if answer in {"ruleset", "transcript"}:
        return answer
    return "unknown"

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _parse_llm_json(content: str) -> dict:
    """Parse JSON from an LLM reply, tolerating markdown fences and surrounding prose."""
    text = _FENCE.sub("", content.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))

def _format_previous(previous_questions: list[str] | None) -> str:
    return "\n".join(previous_questions) if previous_questions else "none"

def decide_search_text(question: str, previous_questions: list[str] | None = None) -> str:
    """Decide which keywords are worth searching for in the user's question.
    """
    try:
        response = completion(
            model=settings.utility_model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": PROMPT_DECIDE_KEYWORDS.format(question=question, previous_questions=_format_previous(previous_questions))}],
        )
        keywords = response.choices[0].message.content.strip()
        return keywords
    except Exception:
        return question  # fallback to the original question if the LLM fails

def decide_date_range(question: str, previous_questions: list[str] | None = None) -> dict[str, date | None] | None:
    try:
        response = completion(
            model=settings.chat_model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": PROMPT_LLM_DECIDE_DATE.format(question=question, previous_questions=_format_previous(previous_questions), today=date.today().isoformat())}],
        )
        print(response.choices[0].message.content)
        raw = _parse_llm_json(response.choices[0].message.content)
        date_range = {key: date.fromisoformat(raw[key]) if raw.get(key) else None for key in ("from", "to")}
        if date_range["from"] is None and date_range["to"] is None:
            return None
        return date_range
    except Exception as e:
        print(f"Error occurred while deciding date range: {e}")
        return None

def understand(question: str, previous_questions: list[str]) -> StructuredQuery:
    result = StructuredQuery(search_text=question, filters=Filters(), scope="narrow")

    prompt = PROMPT.format(today=date.today().isoformat(), question=question)

    match decide_type(question):
        case "ruleset":
            result.filters.doc_type = "ruleset"
        case "transcript":
            result.filters.doc_type = "transcript"
        case "unknown":
            match decide_type_expensive(question):
                case "ruleset":
                    result.filters.doc_type = "ruleset"
                case "transcript":
                    result.filters.doc_type = "transcript"
                case "unknown":
                    result.filters.doc_type = None
                    result.scope = "broad"  

    match decide_scope(question):
        case "narrow":
            result.scope = "narrow"
        case "broad":
            result.scope = "broad"
        case "unknown":
            result.scope = "broad"  # default to broad if we can't tell

    if result.filters.doc_type == "transcript":
        date_range = decide_date_range(question, previous_questions)
        if date_range:
            result.filters.session_date_from = date_range.get("from")
            result.filters.session_date_to = date_range.get("to")

    return result

if __name__ == "__main__":
    print(decide_type("Who uses the fireball spell the most?"))