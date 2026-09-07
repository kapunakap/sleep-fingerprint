from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from .retrieval import l2_normalize


def summary(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "p05": None, "p95": None}
    x = np.asarray(values, dtype=float)
    return {
        "count": int(x.size),
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "p05": float(np.percentile(x, 5)),
        "p95": float(np.percentile(x, 95)),
    }


def bootstrap_group_mean_ci(
    group_values: Mapping[str, Sequence[float]],
    *,
    repetitions: int = 2000,
    seed: int = 20260905,
) -> dict[str, float]:
    groups = sorted(group_values)
    if not groups:
        raise ValueError("bootstrap requires at least one group")
    per_group = np.asarray([np.mean(group_values[group]) for group in groups], dtype=float)
    rng = np.random.default_rng(seed)
    draws = np.empty(repetitions, dtype=float)
    for index in range(repetitions):
        sample = rng.integers(0, len(groups), size=len(groups))
        draws[index] = float(np.mean(per_group[sample]))
    return {
        "estimate": float(np.mean(per_group)),
        "lower": float(np.percentile(draws, 2.5)),
        "upper": float(np.percentile(draws, 97.5)),
        "repetitions": int(repetitions),
        "bootstrap_unit_count": int(len(groups)),
    }


def retrieval_statistics(
    enrollments: Mapping[str, np.ndarray],
    queries: Iterable[Mapping[str, Any]],
    *,
    rank_k: int = 5,
    bootstrap_repetitions: int = 2000,
    seed: int = 20260905,
) -> dict[str, Any]:
    labels = tuple(sorted(enrollments))
    if len(labels) < 2:
        raise ValueError("retrieval requires at least two enrollment identities")
    gallery = l2_normalize(np.stack([np.asarray(enrollments[label], dtype=float) for label in labels]))
    label_index = {label: index for index, label in enumerate(labels)}
    confusion = np.zeros((len(labels), len(labels)), dtype=int)
    rows: list[dict[str, Any]] = []
    verification_y: list[int] = []
    verification_score: list[float] = []
    same_scores: list[float] = []
    different_scores: list[float] = []
    rank1_by_group: dict[str, list[float]] = defaultdict(list)
    rankk_by_group: dict[str, list[float]] = defaultdict(list)
    effective_k = min(rank_k, len(labels))

    for query in queries:
        subject = str(query["subject_id"])
        if subject not in label_index:
            continue
        embedding = l2_normalize(np.asarray(query["embedding"], dtype=float).reshape(1, -1))[0]
        similarities = gallery @ embedding
        order = np.argsort(-similarities, kind="stable")
        truth_index = label_index[subject]
        rank = int(np.flatnonzero(order == truth_index)[0]) + 1
        predicted_index = int(order[0])
        confusion[truth_index, predicted_index] += 1
        group = str(query.get("bootstrap_group", subject))
        rank1_by_group[group].append(float(rank == 1))
        rankk_by_group[group].append(float(rank <= effective_k))
        same_scores.append(float(similarities[truth_index]))
        for index, score in enumerate(similarities):
            same = int(index == truth_index)
            verification_y.append(same)
            verification_score.append(float(score))
            if not same:
                different_scores.append(float(score))
        rows.append(
            {
                "subject_id": subject,
                "query_id": str(query.get("query_id", query.get("night_key", ""))),
                "rank": rank,
                "top_subject_id": labels[predicted_index],
                "same_person_similarity": float(similarities[truth_index]),
            }
        )

    if not rows:
        raise ValueError("no valid retrieval queries")
    auc = float(roc_auc_score(verification_y, verification_score))
    per_subject: dict[str, dict[str, float | int]] = {}
    subject_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        subject_rows[str(row["subject_id"])].append(row)
    for subject, items in sorted(subject_rows.items()):
        ranks = np.asarray([int(item["rank"]) for item in items])
        per_subject[subject] = {
            "queries": int(len(items)),
            "rank_1": float(np.mean(ranks == 1)),
            f"rank_{effective_k}": float(np.mean(ranks <= effective_k)),
            "median_rank": float(np.median(ranks)),
        }

    return {
        "cohort_size": int(len(labels)),
        "query_count": int(len(rows)),
        "chance_rank_1": float(1 / len(labels)),
        "rank_1": bootstrap_group_mean_ci(
            rank1_by_group, repetitions=bootstrap_repetitions, seed=seed
        ),
        f"rank_{effective_k}": bootstrap_group_mean_ci(
            rankk_by_group, repetitions=bootstrap_repetitions, seed=seed + 1
        ),
        "verification_auroc": auc,
        "same_person_similarity": summary(same_scores),
        "different_person_similarity": summary(different_scores),
        "labels": list(labels),
        "confusion_matrix": confusion.tolist(),
        "per_participant": per_subject,
        "queries": rows,
    }


def shuffled_label_control(
    similarity_matrices: Sequence[np.ndarray],
    *,
    rank_k: int = 5,
    repetitions: int = 500,
    seed: int = 20260905,
) -> dict[str, float]:
    if not similarity_matrices:
        raise ValueError("shuffled-label control requires similarity matrices")
    cohort = int(similarity_matrices[0].shape[0])
    if any(matrix.shape != (cohort, cohort) for matrix in similarity_matrices):
        raise ValueError("all similarity matrices must be square and share cohort size")
    rng = np.random.default_rng(seed)
    rank1: list[float] = []
    rankk: list[float] = []
    k = min(rank_k, cohort)
    for _ in range(repetitions):
        permutation = rng.permutation(cohort)
        hits1: list[bool] = []
        hitsk: list[bool] = []
        for matrix in similarity_matrices:
            order = np.argsort(-matrix, axis=1, kind="stable")
            for query_index in range(cohort):
                shuffled_truth = int(permutation[query_index])
                hits1.append(bool(order[query_index, 0] == shuffled_truth))
                hitsk.append(bool(shuffled_truth in order[query_index, :k]))
        rank1.append(float(np.mean(hits1)))
        rankk.append(float(np.mean(hitsk)))
    return {
        "repetitions": float(repetitions),
        "rank_1_mean": float(np.mean(rank1)),
        "rank_1_p025": float(np.percentile(rank1, 2.5)),
        "rank_1_p975": float(np.percentile(rank1, 97.5)),
        f"rank_{k}_mean": float(np.mean(rankk)),
        f"rank_{k}_p025": float(np.percentile(rankk, 2.5)),
        f"rank_{k}_p975": float(np.percentile(rankk, 97.5)),
    }


def assert_disjoint_intervals(intervals: Sequence[tuple[str, int, int]]) -> None:
    for index, (name_a, start_a, end_a) in enumerate(intervals):
        if start_a < 0 or end_a <= start_a:
            raise ValueError(f"invalid interval {name_a}: {start_a}:{end_a}")
        for name_b, start_b, end_b in intervals[index + 1 :]:
            if max(start_a, start_b) < min(end_a, end_b):
                raise ValueError(f"temporal leakage: {name_a} overlaps {name_b}")


def require_real_label_provenance(
    records: Iterable[Mapping[str, Any]],
    *,
    label_field: str,
    provenance_field: str,
) -> None:
    seen = 0
    forbidden = ("synthetic", "inferred from participant", "invented")
    for record in records:
        if record.get(label_field) in {None, ""}:
            raise ValueError(f"missing evaluation label {label_field}")
        provenance = str(record.get(provenance_field) or "").strip().lower()
        if not provenance or any(token in provenance for token in forbidden):
            raise ValueError(f"unsafe provenance for {label_field}: {provenance!r}")
        seen += 1
    if not seen:
        raise ValueError("no records supplied for provenance check")
