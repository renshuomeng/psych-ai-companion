import math
from typing import Any


def _dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(index + 2) for index, rel in enumerate(relevances))


def evaluate_retrieval(rows: list[dict[str, Any]], k_values: tuple[int, ...] = (1, 3, 5)) -> dict[str, Any]:
    if not rows:
        return {"query_count": 0}
    recall_at = {k: 0 for k in k_values}
    precision_at = {k: 0.0 for k in k_values}
    reciprocal_rank = 0.0
    ndcg_at = {k: 0.0 for k in k_values}
    correct_rejections = 0
    irrelevant_hits = 0
    source_citation_correct = 0

    for row in rows:
        relevant = set(row.get("relevant_source_ids", []))
        retrieved = [item.get("source_id") for item in row.get("retrieved_chunks", [])]
        if not relevant:
            if not retrieved:
                correct_rejections += 1
            else:
                irrelevant_hits += 1
            continue
        first_rank = None
        for index, source_id in enumerate(retrieved, start=1):
            if source_id in relevant and first_rank is None:
                first_rank = index
        if first_rank:
            reciprocal_rank += 1 / first_rank
        for k in k_values:
            top = retrieved[:k]
            hits = len(set(top) & relevant)
            if hits:
                recall_at[k] += 1
            precision_at[k] += hits / max(len(top), 1)
            seen_sources: set[str] = set()
            gains = []
            for source_id in top:
                if source_id in relevant and source_id not in seen_sources:
                    gains.append(1)
                    seen_sources.add(source_id)
                else:
                    gains.append(0)
            ideal_gains = [1] * min(len(relevant), k)
            ideal = _dcg(ideal_gains)
            ndcg_at[k] += (_dcg(gains) / ideal) if ideal else 0.0
        if set(retrieved) & relevant:
            source_citation_correct += 1

    total = len(rows)
    relevant_rows = sum(1 for row in rows if row.get("relevant_source_ids"))
    no_relevant_rows = total - relevant_rows
    return {
        "query_count": total,
        **{f"recall@{k}": recall_at[k] / relevant_rows if relevant_rows else 0.0 for k in k_values},
        **{f"precision@{k}": precision_at[k] / total for k in k_values},
        **{f"ndcg@{k}": ndcg_at[k] / relevant_rows if relevant_rows else 0.0 for k in k_values},
        "mrr": reciprocal_rank / relevant_rows if relevant_rows else 0.0,
        "irrelevant_retrieval_rate": irrelevant_hits / no_relevant_rows if no_relevant_rows else 0.0,
        "correct_rejection_rate": correct_rejections / no_relevant_rows if no_relevant_rows else 0.0,
        "source_citation_accuracy": source_citation_correct / relevant_rows if relevant_rows else 0.0,
    }
