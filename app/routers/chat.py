import json
import re
import sys
import uuid

from fastapi import APIRouter, Depends, Request
from litellm import acompletion
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.auth import get_current_user
from app.config import settings
from app.generation.answer import SYSTEM, generate, verify_citations
from app.generation.context import build_context
from app.limiter import limiter
from app.retrieval.rerank import rerank
from app.retrieval.search import hybrid_search
from app.schemas import AnswerOut, Citation

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


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


@router.post("/chat")
@limiter.limit("1/minute")
async def chat(
    body: ChatRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user),
):
    def retrieve():
        """Blocking retrieval pipeline -- kept off the event loop."""
        candidates = hybrid_search(user_id, body.question)
        top = rerank(body.question, candidates)
        return build_context(top)

    async def event_stream():

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

    return EventSourceResponse(event_stream())

@router.post("/chat_waiting", response_model=AnswerOut)
async def chat_waiting(
    body: ChatRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user),
):
    candidates = hybrid_search(user_id, body.question)
    top = rerank(body.question, candidates)
    context, used = build_context(top)
    answer_text, verified = generate(body.question, context, len(used))
    citations = to_citations(used)
    citations = prune_citations(citations, answer_text)
    return AnswerOut(
        answer=answer_text,
        citations=citations,
        verified=verified
    )


if __name__ == "__main__":
    import asyncio

    q = " ".join(sys.argv[1:]) or "how many LI are there in the game"
    mock_user_id = uuid.UUID(int=0)  # 00000000-0000-0000-0000-000000000000
    result = asyncio.run(
        chat_waiting(ChatRequest(question=q), request=None, user_id=mock_user_id)
    )
    print(result.model_dump_json(indent=2))
    