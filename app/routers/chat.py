import json
import re
import sys
import uuid

from fastapi import APIRouter, Depends, Request
from litellm import acompletion, completion
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.auth import get_current_user
from app.config import settings
from app.db.session import session_for_user
from app.generation.answer import SYSTEM, generate, verify_citations
from app.generation.context import build_context
from app.limiter import limiter
from app.retrieval.rerank import rerank
from app.retrieval.search import hybrid_search_pre_understood
from app.routers.conversations import (ConversationCreate, MessageCreate,
                                       create_conversation, create_message)
from app.schemas import AnswerOut, Citation

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
        candidates = hybrid_search_pre_understood(user_id, body.question)
        top = rerank(body.question, candidates)
        return build_context(top)

    async def event_stream():
        # First, so the client can send it back with its next question.
        yield {"event": "conversation", "data": str(conversation_id)}

        context, used = await run_in_threadpool(retrieve)

        stream = await acompletion(
            model=settings.chat_model,
            temperature=settings.temperature,
            stream=True,
            messages=[
                {"role": "system", "content": SYSTEM},
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
        citations = to_citations(used)
        citations = prune_citations(citations, answer_text)
        citations = [c.model_dump(mode="json") for c in citations]
        yield {
            "event": "citations",
            "data": json.dumps({
                "citations": citations,
                "verified": not verify_citations(answer_text, len(used)),
            }),
        }
        #when the whole answer is back, add assistant message to db, with conversation_id, answer_text, citations, and timestamp, the character = "bot"

    # Own session (not Depends) so these rows commit before streaming starts;
    # a yield dependency would only commit after the whole stream finishes.
    with session_for_user(user_id) as db:
        conversation_id = body.conversation_id
        if conversation_id is None:
            title = await run_in_threadpool(_generate_title, body.question)
            conv = await create_conversation(
                ConversationCreate(title=title[:120]), user_id=user_id, db=db)
            conversation_id = conv.id
        await create_message(
            conversation_id,
            MessageCreate(content=body.question, role="user", model_used=None),
            user_id=user_id, db=db,
        )

    return EventSourceResponse(event_stream())
    