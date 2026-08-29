from collections import defaultdict

K = 60


def reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = K,
                           limit: int = 30) -> list[dict]:
    """Design doc section 7.1. Ranks only -- scores are never comparable."""
    scores: dict[str, float] = defaultdict(float)
    by_id: dict[str, dict] = {}

    for results in result_lists:
        for rank, row in enumerate(results, start=1):
            cid = str(row["id"])
            scores[cid] += 1.0 / (k + rank)
            by_id.setdefault(cid, row)

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    out = []
    for cid, score in ranked[:limit]:
        row = dict(by_id[cid])
        row["rrf_score"] = score
        out.append(row)
    return out