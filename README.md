# Design Document — Grounded Q&A over Private Game Materials

**Working name:** Loremaster
**Purpose of the project:** learning how to integrate LLMs with a real-world use case.
**Status:** design locked, not yet implemented.

---

## 1. What the system does

A user signs up, uploads their tabletop RPG materials (rulebooks, house rules, session transcripts), and asks questions in natural language. The system answers **only** from that user's own uploaded materials, cites which document and passage each claim came from, and says "I don't know" when the materials don't contain the answer.

Two representative queries drive the whole design:

| Query | Shape | What it stresses |
|---|---|---|
| "What are the injury types in ruleset X?" | Broad, aggregative, scoped to one document | Needs *many* passages from *one* document; a naive top-5 retrieval will return a partial list and the model will confidently present it as complete |
| "Was Peter's character a warlock in our March 2025 session?" | Narrow, factual, filtered by metadata | Needs exact keyword match on a proper noun ("Peter") plus a date filter; pure semantic similarity is bad at proper nouns |


---

## 2. Stack — locked

| Layer | Choice |
|---|---|
| Backend | **Python 3.12 + FastAPI** | 
| ORM / migrations | **SQLAlchemy 2.0 + Alembic** | 
| Database | **PostgreSQL + `pgvector`** |
| Hosting (DB + auth + files) | **Supabase** |
| Auth | **Supabase Auth**, JWT verified in FastAPI | 
| RAG orchestration | **Hand-written** |
| PDF parsing | **PyMuPDF** (`pymupdf4llm`) | 
| Tokenization | **tiktoken** | 
| Background jobs | **ARQ** (Redis-backed) |
| Frontend | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** | 
| Backend hosting | **Railway** or **Render** | 
| Frontend hosting | **Vercel** |

### Explicitly rejected

- **LangChain / LlamaIndex for retrieval.** The goal is to learn retrieval
