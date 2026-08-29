from app.ingestion.tokens import count_tokens

BUDGET = 12000   # leave room for the system prompt, question, and answer


def build_context(chunks: list[dict], budget: int = BUDGET):
    """Numbered sources with provenance. Design doc section 8, mechanism 1."""
    parts, used, included = [], 0, []

    for chunk in chunks:
        pages = (f"p.{chunk['page_from']}"
                 if chunk["page_from"] == chunk["page_to"]
                 else f"pp.{chunk['page_from']}-{chunk['page_to']}")
        header = f'({chunk["title"]}, {pages}, "{chunk["heading_path"] or ""}")'
        body = f'[{len(included) + 1}] {header}\n{chunk["content"]}'

        cost = count_tokens(body)
        if used + cost > budget:
            break
        parts.append(body)
        included.append(chunk)
        used += cost

    return "\n\n".join(parts), included

if __name__ == "__main__":
    import uuid
    from app.retrieval.search import vector_search
    user_id = "00000000-0000-0000-0000-000000000000"
    search_result = vector_search(uuid.UUID(user_id), "how many LI there are in the game", 3)
    print(build_context(search_result))