from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import butter, detrend, sosfiltfilt, welch
from sklearn.preprocessing import StandardScaler

from .baseline import handcrafted_window_features
from .dataset import ManifestRecord, parse_bcg_csv
from .experiment import retrieval_statistics
from .manifest import primary_manifest_record
from .preprocess import PreprocessConfig, iter_night_windows, resample_signal
from .retrieval import l2_normalize
from .split import NightAssignment, SplitResult


def make_chronological_half_split(records: Iterable[Mapping[str, Any]]) -> SplitResult:
    """Chronological first half train, then held-out validation/test halves."""
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_subject[str(record["subject_id"])].append(dict(record))
    assignments: list[NightAssignment] = []
    exclusions: list[dict[str, Any]] = []
    for subject in sorted(by_subject):
        nights = sorted(
            by_subject[subject],
            key=lambda item: (str(item.get("night_date", "")), str(item["night_key"])),
        )
        if len(nights) < 5:
            exclusions.append({"subject_id": subject, "nights": len(nights), "reason": "needs >=5 nights"})
            continue
        train_count = len(nights) // 2
        heldout = len(nights) - train_count
        val_count = (heldout + 1) // 2
        layout = ["train"] * train_count + ["val"] * val_count + ["test"] * (heldout - val_count)
        for record, split in zip(nights, layout, strict=True):
            assignments.append(
                NightAssignment(
                    subject_id=subject,
                    night_key=str(record["night_key"]),
                    split=split,
                    source_path=str(record.get("source_path") or ""),
                )
            )
    return SplitResult(seed=0, assignments=tuple(assignments), exclusions=tuple(exclusions))


def _raw_components(segment: np.ndarray, fs_hz: float) -> np.ndarray:
    values = detrend(np.asarray(segment, dtype=np.float64), type="linear")
    resp_sos = butter(4, (0.08, 0.7), btype="bandpass", fs=fs_hz, output="sos")
    card_sos = butter(4, (0.7, 15.0), btype="bandpass", fs=fs_hz, output="sos")
    return np.stack([sosfiltfilt(resp_sos, values), sosfiltfilt(card_sos, values)])


def _autocorrelation_features(two_channel: np.ndarray, fs_hz: float) -> np.ndarray:
    values: list[float] = []
    for channel in np.asarray(two_channel, dtype=np.float64):
        centered = channel - float(np.mean(channel))
        denom = float(np.dot(centered, centered))
        for seconds in (0.25, 0.5, 0.75, 1.0, 1.25):
            lag = int(round(seconds * fs_hz))
            numerator = float(np.dot(centered[:-lag], centered[lag:])) if lag < centered.size else 0.0
            values.append(numerator / max(denom, np.finfo(float).tiny))
    return np.asarray(values, dtype=np.float64)


def _spectral_peak_bpm(channel: np.ndarray, fs_hz: float, low_hz: float, high_hz: float) -> float | None:
    frequencies, power = welch(channel, fs=fs_hz, nperseg=min(channel.size, int(round(16 * fs_hz))))
    mask = (frequencies >= low_hz) & (frequencies <= high_hz)
    if np.count_nonzero(mask) < 2:
        return None
    candidate_f = frequencies[mask]
    candidate_p = power[mask]
    return float(candidate_f[int(np.argmax(candidate_p))] * 60.0)


def _deterministic_half(indices: list[int], night_key: str) -> list[int]:
    if len(indices) <= 2:
        return indices
    seed = int.from_bytes(hashlib.sha256(night_key.encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    chosen = rng.choice(indices, size=max(2, len(indices) // 2), replace=False)
    return sorted(int(index) for index in chosen)


def _aggregate(features: list[np.ndarray], indices: list[int], max_windows: int = 12) -> np.ndarray:
    if not indices:
        raise ValueError("cannot aggregate zero windows")
    active = indices
    if len(active) > max_windows:
        positions = np.linspace(0, len(active) - 1, max_windows, dtype=int)
        active = [active[int(position)] for position in sorted(set(positions.tolist()))]
    return np.median(np.stack([features[index] for index in active]), axis=0)


def _edge_signature(values: np.ndarray, fs_hz: float, *, from_end: bool) -> str:
    count = min(values.size, int(round(10 * fs_hz)))
    edge = np.asarray(values[-count:] if from_end else values[:count], dtype=np.float64)
    median = float(np.median(edge))
    mad = float(np.median(np.abs(edge - median)))
    scale = 1.4826 * mad or float(np.std(edge)) or 1.0
    normalized = np.round((edge - median) / scale, decimals=4).astype("<f4", copy=False)
    return hashlib.sha256(normalized.tobytes()).hexdigest()


def _start_hour(timestamp: Any) -> float | None:
    if not timestamp:
        return None
    try:
        value = pd.Timestamp(str(timestamp))
    except ValueError:
        return None
    return float(value.hour + value.minute / 60.0 + value.second / 3600.0)


def extract_primary_night_features(
    manifest: Iterable[Mapping[str, Any]],
    dataset_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    config = PreprocessConfig()
    rows: list[dict[str, Any]] = []
    physiology_rows: list[dict[str, Any]] = []
    for record in manifest:
        night_key = str(record["night_key"])
        path = dataset_root / str(record["source_path"])
        parsed = parse_bcg_csv(path)
        resampled = resample_signal(parsed.signal, parsed.source_fs_hz, config.target_fs_hz)
        accepted_windows = [
            window
            for window in iter_night_windows(parsed.signal, parsed.source_fs_hz, config)
            if window.accepted
        ]
        if not accepted_windows:
            continue
        normalized_features: list[np.ndarray] = []
        cardiac_features: list[np.ndarray] = []
        respiratory_features: list[np.ndarray] = []
        spectral_features: list[np.ndarray] = []
        morphology_features: list[np.ndarray] = []
        amplitude_features: list[np.ndarray] = []
        cardiac_bpm: list[float] = []
        respiratory_bpm: list[float] = []
        for window in accepted_windows:
            two_channel = window.signal
            combined = handcrafted_window_features(two_channel, config.target_fs_hz)
            normalized_features.append(combined)
            respiratory_features.append(combined[:7])
            cardiac_features.append(combined[7:])
            spectral_features.append(combined[[5, 6, 12, 13]])
            morphology_features.append(
                np.concatenate([combined, _autocorrelation_features(two_channel, config.target_fs_hz)])
            )
            raw_segment = resampled[window.start_sample : window.end_sample]
            amplitude_features.append(
                handcrafted_window_features(_raw_components(raw_segment, config.target_fs_hz), config.target_fs_hz)
            )
            heart = _spectral_peak_bpm(two_channel[1], config.target_fs_hz, 0.7, 3.0)
            respiration = _spectral_peak_bpm(two_channel[0], config.target_fs_hz, 0.08, 0.7)
            if heart is not None:
                cardiac_bpm.append(heart)
            if respiration is not None:
                respiratory_bpm.append(respiration)

        all_indices = list(range(len(accepted_windows)))
        early_indices = all_indices[: min(12, len(all_indices))]
        late_indices = all_indices[max(0, len(all_indices) - 12) :]
        random_indices = _deterministic_half(all_indices, night_key)
        features = {
            "combined_normalized": _aggregate(normalized_features, all_indices),
            "cardiac_only": _aggregate(cardiac_features, all_indices),
            "respiratory_only": _aggregate(respiratory_features, all_indices),
            "phase_insensitive_spectral": _aggregate(spectral_features, all_indices),
            "morphology_heavy": _aggregate(morphology_features, all_indices),
            "amplitude_bearing": _aggregate(amplitude_features, all_indices),
            "combined_early": _aggregate(normalized_features, early_indices, max_windows=12),
            "combined_late": _aggregate(normalized_features, late_indices, max_windows=12),
            "combined_random_half": _aggregate(normalized_features, random_indices, max_windows=12),
        }
        start_timestamp = record.get("start_timestamp_utc_plus_08")
        rows.append(
            {
                "subject_id": str(record["subject_id"]),
                "night_key": night_key,
                "night_date": str(record.get("night_date") or ""),
                "source_path": str(record["source_path"]),
                "duration_seconds": float(record["duration_seconds"]),
                "start_timestamp_utc_plus_08": start_timestamp,
                "start_hour": _start_hour(start_timestamp),
                "accepted_windows": len(accepted_windows),
                "left_edge_signature": _edge_signature(resampled, config.target_fs_hz, from_end=False),
                "right_edge_signature": _edge_signature(resampled, config.target_fs_hz, from_end=True),
                "features": features,
                "median_bcg_heart_bpm": float(np.median(cardiac_bpm)) if cardiac_bpm else None,
                "median_bcg_resp_bpm": float(np.median(respiratory_bpm)) if respiratory_bpm else None,
            }
        )
        physiology_rows.append(
            {
                "subject_id": str(record["subject_id"]),
                "night_key": night_key,
                "bcg_heart_bpm": float(np.median(cardiac_bpm)) if cardiac_bpm else None,
                "bcg_resp_bpm": float(np.median(respiratory_bpm)) if respiratory_bpm else None,
            }
        )
    return rows, physiology_rows


def _prepare_retrieval(
    rows: list[dict[str, Any]],
    split: SplitResult,
    *,
    train_feature: str,
    query_feature: str,
) -> tuple[dict[str, np.ndarray], dict[str, list[dict[str, Any]]]]:
    split_by_night = split.by_night()
    train_rows = [row for row in rows if split_by_night.get(str(row["night_key"])) == "train"]
    if not train_rows:
        raise ValueError("no train rows")
    scaler = StandardScaler().fit(np.stack([row["features"][train_feature] for row in train_rows]))
    by_subject: dict[str, list[np.ndarray]] = defaultdict(list)
    for row in train_rows:
        embedding = l2_normalize(scaler.transform(row["features"][train_feature].reshape(1, -1)))[0]
        by_subject[str(row["subject_id"])].append(embedding)
    enrollments = {
        subject: l2_normalize(np.mean(vectors, axis=0).reshape(1, -1))[0]
        for subject, vectors in by_subject.items()
    }
    queries: dict[str, list[dict[str, Any]]] = {"val": [], "test": []}
    for row in rows:
        split_name = split_by_night.get(str(row["night_key"]))
        if split_name not in queries:
            continue
        embedding = l2_normalize(scaler.transform(row["features"][query_feature].reshape(1, -1)))[0]
        queries[split_name].append(
            {
                "subject_id": str(row["subject_id"]),
                "night_key": str(row["night_key"]),
                "query_id": str(row["night_key"]),
                "bootstrap_group": str(row["subject_id"]),
                "embedding": embedding,
            }
        )
    return enrollments, queries


def evaluate_feature_variant(
    rows: list[dict[str, Any]],
    split: SplitResult,
    *,
    train_feature: str,
    query_feature: str | None = None,
    bootstrap_repetitions: int = 2000,
) -> dict[str, Any]:
    query_name = query_feature or train_feature
    enrollments, queries = _prepare_retrieval(
        rows,
        split,
        train_feature=train_feature,
        query_feature=query_name,
    )
    return {
        split_name: retrieval_statistics(
            enrollments,
            query_rows,
            bootstrap_repetitions=bootstrap_repetitions,
            seed=20260905 if split_name == "val" else 20260906,
        )
        for split_name, query_rows in queries.items()
    }


def shuffled_label_control(
    rows: list[dict[str, Any]],
    split: SplitResult,
    *,
    feature: str = "combined_normalized",
    repetitions: int = 500,
    seed: int = 20260905,
) -> dict[str, Any]:
    enrollments, query_map = _prepare_retrieval(rows, split, train_feature=feature, query_feature=feature)
    labels = sorted(enrollments)
    gallery = l2_normalize(np.stack([enrollments[label] for label in labels]))
    label_index = {label: index for index, label in enumerate(labels)}
    rng = np.random.default_rng(seed)
    output: dict[str, Any] = {}
    for split_name, queries in query_map.items():
        similarities = np.stack([gallery @ np.asarray(query["embedding"], dtype=float) for query in queries])
        orders = np.argsort(-similarities, axis=1, kind="stable")
        true_indices = np.asarray([label_index[str(query["subject_id"])] for query in queries], dtype=int)
        rank1: list[float] = []
        rank5: list[float] = []
        for _ in range(repetitions):
            permutation = rng.permutation(len(labels))
            shuffled_truth = permutation[true_indices]
            rank1.append(float(np.mean(orders[:, 0] == shuffled_truth)))
            rank5.append(
                float(
                    np.mean(
                        [truth in orders[index, : min(5, len(labels))] for index, truth in enumerate(shuffled_truth)]
                    )
                )
            )
        output[split_name] = {
            "repetitions": repetitions,
            "rank_1_mean": float(np.mean(rank1)),
            "rank_1_p025": float(np.percentile(rank1, 2.5)),
            "rank_1_p975": float(np.percentile(rank1, 97.5)),
            "rank_5_mean": float(np.mean(rank5)),
            "rank_5_p025": float(np.percentile(rank5, 2.5)),
            "rank_5_p975": float(np.percentile(rank5, 97.5)),
        }
    return output


def evaluate_scalar_shortcut(
    rows: list[dict[str, Any]],
    split: SplitResult,
    *,
    value_field: str,
) -> dict[str, Any]:
    split_by_night = split.by_night()
    train = [
        row
        for row in rows
        if split_by_night.get(str(row["night_key"])) == "train" and row.get(value_field) is not None
    ]
    by_subject: dict[str, list[float]] = defaultdict(list)
    for row in train:
        by_subject[str(row["subject_id"])].append(float(row[value_field]))
    subjects = sorted(by_subject)
    centers = np.asarray([np.mean(by_subject[subject]) for subject in subjects], dtype=float)
    scale = float(np.std(centers)) or 1.0
    output: dict[str, Any] = {}
    for split_name in ("val", "test"):
        ranks: list[int] = []
        for row in rows:
            if split_by_night.get(str(row["night_key"])) != split_name or row.get(value_field) is None:
                continue
            subject = str(row["subject_id"])
            if subject not in subjects:
                continue
            scores = -np.abs((centers - float(row[value_field])) / scale)
            order = np.argsort(-scores, kind="stable")
            ranks.append(int(np.flatnonzero(order == subjects.index(subject))[0]) + 1)
        output[split_name] = {
            "query_count": len(ranks),
            "rank_1": float(np.mean(np.asarray(ranks) == 1)) if ranks else None,
            "rank_5": float(np.mean(np.asarray(ranks) <= min(5, len(subjects)))) if ranks else None,
            "chance_rank_1": float(1 / len(subjects)) if subjects else None,
        }
    return output


def duplicate_signature_collisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in rows:
        for edge in ("left", "right"):
            grouped[str(row[f"{edge}_edge_signature"])].append((str(row["night_key"]), edge))
    return [
        {"signature": signature, "occurrences": occurrences}
        for signature, occurrences in grouped.items()
        if len(occurrences) > 1
    ]


def installation_aware_primary_manifest(records: Iterable[ManifestRecord]) -> list[dict[str, Any]]:
    return [
        asdict(
            primary_manifest_record(
                participant_id=record.subject_id,
                night_id=record.night_date,
                source_path=record.source_path,
                recording_date=record.night_date,
            )
        )
        for record in records
    ]


def summarize_split(split: SplitResult) -> dict[str, Any]:
    counts = Counter(assignment.split for assignment in split.assignments)
    per_subject = Counter(assignment.subject_id for assignment in split.assignments)
    return {
        "train_nights": int(counts.get("train", 0)),
        "val_nights": int(counts.get("val", 0)),
        "test_nights": int(counts.get("test", 0)),
        "subjects": len(per_subject),
        "exclusions": list(split.exclusions),
    }


def _find_reference_file(dataset_root: Path, record: Mapping[str, Any], kind: str) -> Path | None:
    bcg_path = dataset_root / str(record["source_path"])
    reference_root = bcg_path.parent.parent / "Reference"
    if not reference_root.exists():
        return None
    date = str(record.get("night_date") or "")
    candidates = [
        path
        for path in reference_root.rglob("*")
        if path.is_file() and path.parent.name.casefold() == kind.casefold() and date in path.name
    ]
    return sorted(candidates)[0] if candidates else None


def add_reference_physiology(
    physiology_rows: list[dict[str, Any]],
    manifest: Iterable[Mapping[str, Any]],
    dataset_root: Path,
) -> list[dict[str, Any]]:
    by_night = {str(row["night_key"]): row for row in physiology_rows}
    for record in manifest:
        target = by_night.get(str(record["night_key"]))
        if target is None:
            continue
        rr_path = _find_reference_file(dataset_root, record, "RR")
        if rr_path is not None:
            try:
                table = pd.read_csv(rr_path, encoding="utf-8-sig")
                columns = {str(column).strip().casefold(): column for column in table.columns}
                hr_column = next(
                    (column for key, column in columns.items() if "heart rate" in key or key == "hr"),
                    None,
                )
                if hr_column is not None:
                    values = pd.to_numeric(table[hr_column], errors="coerce").dropna().to_numpy(dtype=float)
                    values = values[(values >= 30) & (values <= 220)]
                    if values.size:
                        target["reference_heart_bpm"] = float(np.median(values))
                        target["reference_heart_samples"] = int(values.size)
            except (OSError, ValueError, pd.errors.ParserError):
                pass
        resp_path = _find_reference_file(dataset_root, record, "resp")
        if resp_path is not None:
            try:
                parsed = parse_bcg_csv(resp_path, default_fs_hz=20.0)
                resp = detrend(parsed.signal, type="linear")
                target["reference_resp_bpm"] = _spectral_peak_bpm(resp, parsed.source_fs_hz, 0.08, 0.7)
                target["reference_resp_samples"] = int(resp.size)
            except (OSError, ValueError):
                pass
    return physiology_rows


def physiology_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for label, estimate_key, reference_key in (
        ("heart_rate", "bcg_heart_bpm", "reference_heart_bpm"),
        ("respiratory_rate", "bcg_resp_bpm", "reference_resp_bpm"),
    ):
        valid = [
            row
            for row in rows
            if row.get(estimate_key) is not None and row.get(reference_key) is not None
        ]
        estimate = np.asarray([float(row[estimate_key]) for row in valid])
        reference = np.asarray([float(row[reference_key]) for row in valid])
        if len(valid) < 3:
            output[label] = {"nights": len(valid), "mae": None, "median_ae": None, "pearson_r": None}
            continue
        output[label] = {
            "nights": len(valid),
            "mae": float(np.mean(np.abs(estimate - reference))),
            "median_ae": float(np.median(np.abs(estimate - reference))),
            "pearson_r": float(np.corrcoef(estimate, reference)[0, 1]),
        }
    return output
