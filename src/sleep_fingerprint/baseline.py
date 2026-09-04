from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from scipy.integrate import trapezoid
from scipy.signal import welch
from scipy.stats import kurtosis, skew
from sklearn.preprocessing import StandardScaler

from .dataset import parse_bcg_csv
from .preprocess import PreprocessConfig, iter_night_windows
from .retrieval import RetrievalEvaluation, evaluate_retrieval, l2_normalize
from .split import SplitResult


def handcrafted_window_features(two_channel: np.ndarray, fs_hz: float = 64.0) -> np.ndarray:
    features: list[float] = []
    for channel in np.asarray(two_channel, dtype=np.float64):
        frequencies, power = welch(channel, fs=fs_hz, nperseg=min(len(channel), int(fs_hz * 16)))
        dominant = float(frequencies[int(np.argmax(power))])
        band_energy = float(trapezoid(power, frequencies))
        features.extend(
            [
                float(np.std(channel)),
                float(np.sqrt(np.mean(np.square(channel)))),
                float(np.median(np.abs(channel - np.median(channel)))),
                float(skew(channel, bias=False)),
                float(kurtosis(channel, fisher=True, bias=False)),
                dominant,
                float(np.log(band_energy + np.finfo(float).tiny)),
            ]
        )
    return np.nan_to_num(np.asarray(features), nan=0.0, posinf=0.0, neginf=0.0)


def run_handcrafted_baseline(
    manifest: Iterable[Mapping[str, Any]],
    split_result: SplitResult,
    dataset_root: Path,
    max_windows_per_night: int = 12,
) -> dict[str, RetrievalEvaluation]:
    split_by_night = split_result.by_night()
    night_rows: list[dict[str, Any]] = []
    config = PreprocessConfig()
    for record in manifest:
        split = split_by_night.get(str(record["night_key"]))
        if split is None:
            continue
        parsed = parse_bcg_csv(dataset_root / str(record["source_path"]))
        accepted = [w.signal for w in iter_night_windows(parsed.signal, parsed.source_fs_hz, config) if w.accepted]
        if not accepted:
            continue
        if len(accepted) > max_windows_per_night:
            positions = np.linspace(0, len(accepted) - 1, max_windows_per_night, dtype=int)
            accepted = [accepted[i] for i in sorted(set(positions.tolist()))]
        feature = np.median(np.stack([handcrafted_window_features(w) for w in accepted]), axis=0)
        night_rows.append({"subject_id": str(record["subject_id"]), "night_key": str(record["night_key"]), "split": split, "feature": feature})
    train = [row for row in night_rows if row["split"] == "train"]
    if not train:
        raise ValueError("no train-night features survived QC")
    scaler = StandardScaler().fit(np.stack([row["feature"] for row in train]))
    for row in night_rows:
        row["embedding"] = l2_normalize(scaler.transform(row["feature"].reshape(1, -1)))[0]
    by_subject: dict[str, list[np.ndarray]] = defaultdict(list)
    for row in night_rows:
        if row["split"] == "train":
            by_subject[row["subject_id"]].append(row["embedding"])
    enrollments = {s: l2_normalize(np.mean(v, axis=0).reshape(1, -1))[0] for s, v in by_subject.items()}
    return {
        split: evaluate_retrieval(enrollments, [row for row in night_rows if row["split"] == split])
        for split in ("val", "test")
    }
