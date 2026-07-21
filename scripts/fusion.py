"""Rank-fusion utilities shared by the app and evaluation scripts."""

from __future__ import annotations


def fuse_ranked_results(
    rankings: list[tuple[float, list[dict[str, str | float]]]],
    top_k: int,
    rank_constant: int = 60,
) -> list[dict[str, str | float]]:
    """Fuse differently scaled result lists with weighted reciprocal rank."""
    if top_k <= 0:
        return []
    if rank_constant < 0:
        raise ValueError("The rank constant must be zero or greater.")
    total_weight = sum(weight for weight, _ in rankings if weight > 0)
    if total_weight <= 0:
        return []

    scores: dict[str, float] = {}
    records: dict[str, dict[str, str | float]] = {}
    for weight, results in rankings:
        if weight <= 0:
            continue
        for rank, result in enumerate(results, start=1):
            item_id = str(result["item_id"])
            scores[item_id] = scores.get(item_id, 0.0) + weight / (
                rank_constant + rank
            )
            records.setdefault(item_id, result)

    maximum = total_weight / (rank_constant + 1)
    ranked_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
    return [
        {
            **records[item_id],
            "score": scores[item_id] / maximum,
            "score_label": "FUSION",
        }
        for item_id in ranked_ids
    ]
