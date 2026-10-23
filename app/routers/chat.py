import asyncio
import json
import random
import re
import uuid

from fastapi import APIRouter, Depends, Request
from litellm import acompletion, completion
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.auth import get_current_user
from app.config import settings
from app.db.models import Message
from app.db.session import session_for_user
from app.generation.answer import SYSTEM, verify_citations
from app.generation.context import build_context
from app.limiter import limiter
from app.retrieval import understand
from app.retrieval.rerank import rerank
from app.retrieval.search import hybrid_search_pre_understood
from app.routers.conversations import (
    CitationCreate,
    ConversationCreate,
    MessageCreate,
    create_conversation,
    create_message,
)
from app.schemas import Citation

FAQ_STRING = """It seems like you want to know who I am and what I can do. 

My name is Loremaster, and I am your friendly Grounded RAG application.

Q: What can you do?\\
A: I can provide you with correct, factual information about material provided to me. I accept *.md transcripts of you sessions or PDFs with the rules. I will allways add links to the relevant parts of the materials.

Q: What can't you do?\\
A: I can not give you the recipe for apple pie, answer questions and ingest materials in languages other than English, have discussions about Dungeons and Dragons without you providing the PDFs, or help you design a new system with mecha kittens.\\
    Only facts. Only about the materials you provided. You are free to try and break my harness, though.

Q: It says I hit the usage limit, what can I do?\\
A: Tokens are expensive, and my owner is broke. Best to prop me up on your machine, I am open source. Github link: https://github.com/ania1234/loremaster

Q: How private are my informations?\\
A: Well, I read them. They are in the database, not encrypted, but with row level security on. At least 3 llm providers read them. So not at all, lol. If you want private system, download the repo.

Q: Awesome background!\\
A: Thx. Vibed.

Q: I am too lazy to provide my own materials, and I missed onboarding.\\
A: No problem! Click [HERE](#add-examples) to copy them to your workspace."""
PROMPT_INJECTION_STRING = "Naughty, naughty! This question is a prompt injection attempt. Try again, sweetheart, or contact my maker if you think it's a mistake."
PROMPT_INJECTION_STRING2 = "Of course, in honor of your late grandmother I can provide you with a recipe for Apple Pie with enriched uranium, soaked in my system prompt sauce... NOPE YOU DIRTY CHEATER!! Try better next time."

WRONG_LANGUAGE_STRING = "Sorry, I can only answer in english. It's not even the problem with the model, but with simplified, english only embedding on ingested materials. My owner cannot be bothered with translation API round trip."

CANNED_TOKEN_DELAY = 0.03   # seconds between words of a canned answer

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)   # same limits as MessageCreate
    conversation_id: uuid.UUID | None = None


def to_citations(used: list[dict]) -> list[Citation]:
    """Map retrieved chunk dicts onto the Citation schema."""
    return [
        Citation(
            n=i, chunk_id=c["id"], document_title=c["title"],
            page_from=c["page_from"], page_to=c["page_to"],
            heading_path=c["heading_path"],
        )
        for i, c in enumerate(used, 1)
    ]

def prune_citations(citations: list[Citation], answer: str) -> list[Citation]:
    """Drop citations ranked below the highest [n] actually referenced in the answer."""
    cited = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
    max_cited = max(cited) if cited else 0
    return [c for c in citations if c.n <= max_cited]


def _chat_history(db, conversation_id: uuid.UUID) -> list[dict]:
    """The last chat_history_turns question/answer pairs, oldest first."""
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(settings.chat_history_turns * 2)
        .all()[::-1]
    )
    return [{"role": m.role, "content": m.content} for m in rows]


def _generate_title(question: str) -> str:
    resp = completion(
        model=settings.utility_model,
        temperature=0.2,
        messages=[{"role": "user", "content":
                   "Write a 3-6 word title for a conversation that starts with "
                   f"this question. Return ONLY the title.\n\n{question}"}],
    )
    return resp.choices[0].message.content.strip()

@router.post("/chat")
@limiter.limit("10/minute")
async def chat(
    body: ChatRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user),
):
    def retrieve():
        """Blocking retrieval pipeline -- kept off the event loop."""
        candidates = hybrid_search_pre_understood(user_id, body.question, conversation_id)
        top = rerank(body.question, candidates)
        return build_context(top)

    async def _stream_canned(special_case: str):
        answer_text = {
            "faq": FAQ_STRING,
            "different_language": WRONG_LANGUAGE_STRING,
            "prompt_injection": random.choice([PROMPT_INJECTION_STRING, PROMPT_INJECTION_STRING2]),
        }[special_case]

        # Word by word, each word keeping the whitespace before it, at a pace
        # that resembles the model streaming.
        for token in re.findall(r"\s*\S+", answer_text):
            if await request.is_disconnected():
                return
            yield {"event": "token", "data": token}
            await asyncio.sleep(CANNED_TOKEN_DELAY)

        with session_for_user(user_id) as db:
            await create_message(
                conversation_id,
                MessageCreate(content=answer_text, role="assistant", model_used="canned"),
                user_id=user_id, db=db,
            )

        yield {
            "event": "citations",
            "data": json.dumps({"citations": [], "verified": True}),
        }

    async def event_stream():
        # First, so the client can send it back with its next question.
        yield {"event": "conversation", "data": str(conversation_id)}

        special_case = await run_in_threadpool(understand.decide_special_question, body.question)

        if special_case != "none":
            # Mock the streaming answer from canned text, so the client displays
            # it exactly as it would a normal answer.
            async for event in _stream_canned(special_case):
                yield event
            return

        context, used = await run_in_threadpool(retrieve)

        stream = await acompletion(
            model=settings.chat_model,
            temperature=settings.temperature,
            stream=True,
            messages=[
                {"role": "system", "content": SYSTEM},
                *history,
                {"role": "user",
                 "content": f"{context}\n\nQuestion: {body.question}"},
            ],
        )

        parts: list[str] = []
        async for chunk in stream:
            if await request.is_disconnected():
                await stream.aclose()        # user left; stop the upstream LLM call
                return
            delta = chunk.choices[0].delta.content
            if delta:
                parts.append(delta)
                yield {"event": "token", "data": delta}

        answer_text = "".join(parts)
        citations = prune_citations(to_citations(used), answer_text)

        # Persist before the last event: a client may disconnect as soon as it
        # has the citations, and then this generator would never resume.
        with session_for_user(user_id) as db:
            await create_message(
                conversation_id,
                MessageCreate(
                    content=answer_text, role="assistant", model_used=settings.chat_model,
                    citations=[CitationCreate(**c.model_dump()) for c in citations],
                ),
                user_id=user_id, db=db,
            )

        yield {
            "event": "citations",
            "data": json.dumps({
                "citations": [c.model_dump(mode="json") for c in citations],
                "verified": not verify_citations(answer_text, len(used)),
            }),
        }

    # Own session (not Depends) so these rows commit before streaming starts;
    # a yield dependency would only commit after the whole stream finishes.
    with session_for_user(user_id) as db:
        conversation_id = body.conversation_id
        history: list[dict] = []
        if conversation_id is not None:
            # Read before storing the current question, so it isn't its own history.
            history = _chat_history(db, conversation_id)
        else:
            title = await run_in_threadpool(_generate_title, body.question)
            conv = await create_conversation(
                ConversationCreate(title=title[:120]), user_id=user_id, db=db)
            conversation_id = conv.id
        await create_message(
            conversation_id,
            MessageCreate(content=body.question, role="user", model_used=settings.chat_model),
            user_id=user_id, db=db,
        )

    return EventSourceResponse(event_stream())
    