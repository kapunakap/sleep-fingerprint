from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np


@dataclass(frozen=True)
class RetrievalEvaluation:
    metrics: dict[str, Any]
    queries: tuple[dict[str, Any], ...]
    labels: tuple[str, ...]
    confusion: np.ndarray | None


def l2_normalize(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=np.float64)
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.maximum(norms, np.finfo(float).eps)


def _summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "p05": None, "p95": None}
    x = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "p05": float(np.percentile(x, 5)),
        "p95": float(np.percentile(x, 95)),
    }


def evaluate_retrieval(
    enrollments: Mapping[str, np.ndarray],
    queries: Iterable[Mapping[str, Any]],
    rank_k: int = 5,
) -> RetrievalEvaluation:
    labels = tuple(sorted(enrollments))
    if not labels:
        raise ValueError("no enrollment identities")
    matrix = l2_normalize(np.stack([enrollments[label] for label in labels]))
    index = {label: i for i, label in enumerate(labels)}
    rows: list[dict[str, Any]] = []
    same: list[float] = []
    different: list[float] = []
    confusion = np.zeros((len(labels), len(labels)), dtype=int) if len(labels) >= 2 else None
    for query in queries:
        subject = str(query["subject_id"])
        if subject not in index:
            continue
        embedding = l2_normalize(np.asarray(query["embedding"]).reshape(1, -1))[0]
        similarities = matrix @ embedding
        order = np.argsort(-similarities, kind="stable")
        truth = index[subject]
        rank = int(np.flatnonzero(order == truth)[0]) + 1
        prediction = int(order[0])
        same.append(float(similarities[truth]))
        different.extend(float(v) for i, v in enumerate(similarities) if i != truth)
        if confusion is not None:
            confusion[truth, prediction] += 1
        rows.append(
            {
                "subject_id": subject,
                "night_key": str(query.get("night_key", "")),
                "rank": rank,
                "top_subject_id": labels[prediction],
                "same_person_similarity": float(similarities[truth]),
            }
        )
    effective_k = min(rank_k, len(labels))
    metrics = {
        "query_nights": len(rows),
        "cohort_size": len(labels),
        "rank_1": float(np.mean([r["rank"] == 1 for r in rows])) if rows else None,
        f"rank_{effective_k}_capped": float(np.mean([r["rank"] <= effective_k for r in rows])) if rows else None,
        "chance_rank_1": 1.0 / len(labels),
        "same_person_similarity": _summary(same),
        "different_person_similarity": _summary(different),
    }
    return RetrievalEvaluation(metrics, tuple(rows), labels, confusion)
