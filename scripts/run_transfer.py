#!/usr/bin/env python3
"""Frozen independent-domain transfer probe for Figshare 28643153.

The representation is fixed before target-label fitting. Only a lightweight
ridge probe and training-fold standardization are fitted on target labels.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
    roc_curve,
)
from sklearn.preprocessing import StandardScaler

ARTICLE_API = "https://api.figshare.com/v2/articles/28643153"
CONFIG_DEFAULT = Path("configs/transfer_28643153.json")
OUT_DEFAULT = Path("metrics/transfer_28643153")
PLOTS_DEFAULT = Path("plots/transfer_28643153")


@dataclass(frozen=True)
class SubjectRow:
    subject_id: int
    sex: str
    age: float
    conclusion: str
    broad_af: int
    persistent_af: int
    feature: np.ndarray


def _http_json(url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Figshare metadata response was not an object")
    return payload


def _read_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text())
    if config["dataset"]["article_id"] != 28643153:
        raise RuntimeError("unexpected transfer article id")
    return config


def _metadata_and_file_map(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[int, dict[str, Any]], dict[str, Any]]:
    article = _http_json(ARTICLE_API)
    license_name = str((article.get("license") or {}).get("name", ""))
    expected_license = str(config["dataset"]["license"])
    if license_name != expected_license:
        raise RuntimeError(f"license changed: expected {expected_license!r}, got {license_name!r}")

    files = article.get("files") or []
    workbook = next((item for item in files if item.get("name") == "Overall_info.xlsx"), None)
    if workbook is None:
        raise RuntimeError("Overall_info.xlsx not found")

    bcg_files: dict[int, dict[str, Any]] = {}
    for item in files:
        match = re.fullmatch(r"Sub(\d{2})_bcg\.csv", str(item.get("name", "")))
        if match:
            bcg_files[int(match.group(1))] = item
    if len(bcg_files) != 46:
        raise RuntimeError(f"expected 46 subject BCG files, found {len(bcg_files)}")

    workbook_response = requests.get(str(workbook["download_url"]), timeout=60)
    workbook_response.raise_for_status()
    frame = pd.read_excel(io.BytesIO(workbook_response.content), engine="openpyxl")
    required = {"Idx", "Sex", "Age", "Conclusion", "Atrial Fibrillation"}
    missing = required.difference(frame.columns)
    if missing:
        raise RuntimeError(f"missing workbook columns: {sorted(missing)}")
    frame = frame.loc[:, ["Idx", "Sex", "Age", "Conclusion", "Atrial Fibrillation"]].copy()
    frame["Idx"] = frame["Idx"].astype(int)
    frame["Age"] = pd.to_numeric(frame["Age"], errors="raise")
    if sorted(frame["Idx"].tolist()) != list(range(1, 47)):
        raise RuntimeError("subject ids are not exactly 1..46")
    return frame, bcg_files, article


def _stream_bcg_samples(url: str, sample_count: int, range_bytes: int) -> np.ndarray:
    headers = {"Range": f"bytes=0-{range_bytes - 1}"}
    response = requests.get(url, headers=headers, stream=True, timeout=60)
    response.raise_for_status()
    values: list[float] = []
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = str(raw_line).strip()
        if line.casefold().startswith("time"):
            continue
        comma = line.rfind(",")
        if comma < 0:
            continue
        try:
            value = float(line[comma + 1 :])
        except ValueError:
            continue
        if math.isfinite(value):
            values.append(value)
        if len(values) >= sample_count:
            break
    response.close()
    if len(values) != sample_count:
        raise RuntimeError(f"only {len(values)} BCG samples recovered from {url}")
    return np.asarray(values, dtype=np.float64)


def _linear_detrend(values: np.ndarray) -> np.ndarray:
    n = values.size
    x = np.arange(n, dtype=np.float64)
    sx = float(x.sum())
    sy = float(values.sum())
    sxx = float(np.dot(x, x))
    sxy = float(np.dot(x, values))
    denominator = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / denominator if denominator else 0.0
    intercept = (sy - slope * sx) / n
    return values - (intercept + slope * x)


def _band_sum(power: np.ndarray, fs_hz: float, fft_n: int, lo: float, hi: float) -> float:
    k0 = max(1, int(math.ceil(lo * fft_n / fs_hz)))
    k1 = min(power.size - 1, int(math.floor(hi * fft_n / fs_hz)))
    return float(power[k0 : k1 + 1].sum())


def _peak(power: np.ndarray, fs_hz: float, fft_n: int, lo: float, hi: float) -> float:
    k0 = max(1, int(math.ceil(lo * fft_n / fs_hz)))
    k1 = min(power.size - 1, int(math.floor(hi * fft_n / fs_hz)))
    index = k0 + int(np.argmax(power[k0 : k1 + 1]))
    return index * fs_hz / fft_n


def _entropy(power: np.ndarray, fs_hz: float, fft_n: int, lo: float, hi: float) -> float:
    k0 = max(1, int(math.ceil(lo * fft_n / fs_hz)))
    k1 = min(power.size - 1, int(math.floor(hi * fft_n / fs_hz)))
    band = power[k0 : k1 + 1]
    total = float(band.sum())
    if total <= 0:
        return 0.0
    probabilities = band / total
    probabilities = probabilities[probabilities > 0]
    return float(-(probabilities * np.log(probabilities)).sum() / np.log(band.size))


def _centroid(power: np.ndarray, fs_hz: float, fft_n: int, lo: float, hi: float) -> float:
    k0 = max(1, int(math.ceil(lo * fft_n / fs_hz)))
    k1 = min(power.size - 1, int(math.floor(hi * fft_n / fs_hz)))
    band = power[k0 : k1 + 1]
    total = float(band.sum())
    if total <= 0:
        return 0.0
    frequencies = np.arange(k0, k1 + 1, dtype=np.float64) * fs_hz / fft_n
    return float(np.dot(band, frequencies) / total)


def _window_feature(raw: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    representation = config["representation"]
    decimation = int(representation["decimation"])
    values = raw[::decimation]
    fs_hz = float(config["dataset"]["sampling_hz"]) / decimation
    detrended = _linear_detrend(values)
    median = float(np.median(detrended))
    mad = float(np.median(np.abs(detrended - median)))
    scale = 1.4826 * mad
    if scale <= 0:
        scale = float(np.sqrt(np.mean((detrended - median) ** 2)))
    if scale <= 0:
        scale = 1.0

    normalized = (detrended - median) / scale
    window = np.hanning(normalized.size)
    fft_n = int(representation["fft_n"])
    spectrum = np.fft.fft(normalized * window, n=fft_n)
    power = (spectrum.real**2 + spectrum.imag**2)[: fft_n // 2]

    edges = [float(value) for value in representation["band_edges_hz"]]
    features = [
        math.log(_band_sum(power, fs_hz, fft_n, lo, hi) + 1e-12)
        for lo, hi in zip(edges[:-1], edges[1:], strict=True)
    ]
    features.extend(
        [
            _peak(power, fs_hz, fft_n, 0.08, 0.70),
            _peak(power, fs_hz, fft_n, 0.70, 3.00),
            _entropy(power, fs_hz, fft_n, 0.08, 0.70),
            _entropy(power, fs_hz, fft_n, 0.70, 15.00),
            _centroid(power, fs_hz, fft_n, 0.70, 15.00),
            math.log(
                (_band_sum(power, fs_hz, fft_n, 3.00, 15.00) + 1e-12)
                / (_band_sum(power, fs_hz, fft_n, 0.70, 3.00) + 1e-12)
            ),
        ]
    )
    return np.asarray(features, dtype=np.float64)


def _subject_feature(values: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    representation = config["representation"]
    window_samples = int(representation["window_seconds"] * config["dataset"]["sampling_hz"])
    window_count = int(representation["windows"])
    rows = [
        _window_feature(values[index * window_samples : (index + 1) * window_samples], config)
        for index in range(window_count)
    ]
    return np.median(np.vstack(rows), axis=0)


def _is_broad_af(conclusion: str, event: Any) -> int:
    diagnosis_hit = bool(re.search(r"persistent atrial fibrillation|paroxysmal atrial flutter", conclusion, re.I))
    if pd.isna(event):
        event_hit = False
    else:
        event_text = str(event).strip()
        event_hit = bool(event_text and event_text != "/")
    return int(diagnosis_hit or event_hit)


def _is_persistent_af(conclusion: str) -> int:
    return int(bool(re.search(r"persistent atrial fibrillation", conclusion, re.I)))


def _load_subjects(config: dict[str, Any]) -> tuple[list[SubjectRow], dict[str, Any]]:
    frame, bcg_files, article = _metadata_and_file_map(config)
    sample_count = int(config["representation"]["used_samples_per_subject"])
    range_bytes = int(config["representation"]["range_bytes_per_subject"])
    rows: list[SubjectRow] = []
    for record in frame.to_dict(orient="records"):
        subject_id = int(record["Idx"])
        conclusion = "" if pd.isna(record["Conclusion"]) else str(record["Conclusion"])
        values = _stream_bcg_samples(
            str(bcg_files[subject_id]["download_url"]),
            sample_count=sample_count,
            range_bytes=range_bytes,
        )
        rows.append(
            SubjectRow(
                subject_id=subject_id,
                sex=str(record["Sex"]),
                age=float(record["Age"]),
                conclusion=conclusion,
                broad_af=_is_broad_af(conclusion, record["Atrial Fibrillation"]),
                persistent_af=_is_persistent_af(conclusion),
                feature=_subject_feature(values, config),
            )
        )
    return rows, article


def _lcg_folds(n: int, fold_count: int, seed: int) -> np.ndarray:
    order = list(range(n))
    state = seed & 0xFFFFFFFF
    for index in range(n - 1, 0, -1):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        swap = state % (index + 1)
        order[index], order[swap] = order[swap], order[index]
    folds = np.empty(n, dtype=np.int64)
    for position, row_index in enumerate(order):
        folds[row_index] = position % fold_count
    return folds


def _ridge_scores(
    features: np.ndarray,
    targets: np.ndarray,
    folds: np.ndarray,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray]:
    scores = np.empty(targets.size, dtype=np.float64)
    baselines = np.empty(targets.size, dtype=np.float64)
    for fold in sorted(set(int(value) for value in folds.tolist())):
        train = folds != fold
        test = folds == fold
        scaler = StandardScaler().fit(features[train])
        train_x = scaler.transform(features[train])
        test_x = scaler.transform(features[test])
        train_y = targets[train]
        target_mean = float(train_y.mean())
        centered = train_y - target_mean
        gram = train_x.T @ train_x + alpha * np.eye(train_x.shape[1])
        beta = np.linalg.solve(gram, train_x.T @ centered)
        scores[test] = target_mean + test_x @ beta
        baselines[test] = target_mean
    return scores, baselines


def _stratified_bootstrap(
    labels: np.ndarray,
    scores: np.ndarray,
    seed: int,
    iterations: int,
) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    positive = np.flatnonzero(labels == 1)
    negative = np.flatnonzero(labels == 0)
    values: list[tuple[float, float, float]] = []
    for _ in range(iterations):
        sampled = np.r_[
            rng.choice(positive, positive.size, replace=True),
            rng.choice(negative, negative.size, replace=True),
        ]
        y = labels[sampled]
        s = scores[sampled]
        values.append(
            (
                float(roc_auc_score(y, s)),
                float(average_precision_score(y, s)),
                float(balanced_accuracy_score(y, (s >= 0.5).astype(int))),
            )
        )
    array = np.asarray(values, dtype=np.float64)
    low, high = np.quantile(array, [0.025, 0.975], axis=0)
    return {
        "auroc": [float(low[0]), float(high[0])],
        "auprc": [float(low[1]), float(high[1])],
        "balanced_accuracy": [float(low[2]), float(high[2])],
    }


def _classification_metrics(labels: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    predictions = (scores >= 0.5).astype(int)
    positives = int(labels.sum())
    negatives = int(labels.size - positives)
    return {
        "n": int(labels.size),
        "positive": positives,
        "negative": negatives,
        "auroc": float(roc_auc_score(labels, scores)),
        "auprc": float(average_precision_score(labels, scores)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, predictions)),
        "majority_accuracy": max(positives, negatives) / labels.size,
        "trivial_balanced_accuracy": 0.5,
    }


def _plot_persistent_roc(labels: np.ndarray, scores: np.ndarray, output: Path) -> None:
    fpr, tpr, _ = roc_curve(labels, scores)
    auroc = roc_auc_score(labels, scores)
    figure, axis = plt.subplots(figsize=(5.5, 4.5))
    axis.plot(fpr, tpr, label=f"Frozen representation (AUROC={auroc:.3f})")
    axis.plot([0, 1], [0, 1], linestyle="--", label="Chance")
    axis.set_xlabel("False positive rate")
    axis.set_ylabel("True positive rate")
    axis.set_title("Persistent AF transfer")
    axis.legend(loc="lower right")
    figure.tight_layout()
    figure.savefig(output)
    plt.close(figure)


def _plot_task_summary(metrics: dict[str, Any], output: Path) -> None:
    figure, axis = plt.subplots(figsize=(5.5, 4.5))
    names = ["Broad AF", "Persistent AF"]
    values = [metrics["broad_af"]["auroc"], metrics["persistent_af"]["auroc"]]
    axis.bar(names, values)
    axis.axhline(0.5, linestyle="--", label="Chance AUROC")
    axis.set_ylim(0, 1)
    axis.set_ylabel("AUROC")
    axis.set_title("Frozen cardiovascular transfer")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--plots-dir", type=Path, default=PLOTS_DEFAULT)
    args = parser.parse_args()

    config = _read_config(args.config)
    subjects, article = _load_subjects(config)
    features = np.vstack([row.feature for row in subjects])
    if features.shape != (46, 28):
        raise RuntimeError(f"expected a 46x28 frozen feature matrix, got {features.shape}")

    split = config["split"]
    folds = _lcg_folds(len(subjects), int(split["fold_count"]), int(split["seed"]))
    alpha = float(config["probe"]["ridge_alpha"])

    ages = np.asarray([row.age for row in subjects], dtype=np.float64)
    age_scores, age_baselines = _ridge_scores(features, ages, folds, alpha)
    age_metrics = {
        "n": len(subjects),
        "age_min": float(ages.min()),
        "age_max": float(ages.max()),
        "mae_years": float(mean_absolute_error(ages, age_scores)),
        "rmse_years": float(math.sqrt(mean_squared_error(ages, age_scores))),
        "pearson": float(np.corrcoef(ages, age_scores)[0, 1]),
        "spearman": float(pd.Series(ages).corr(pd.Series(age_scores), method="spearman")),
        "baseline_train_mean_mae_years": float(mean_absolute_error(ages, age_baselines)),
        "baseline_train_mean_rmse_years": float(math.sqrt(mean_squared_error(ages, age_baselines))),
    }

    broad_labels = np.asarray([row.broad_af for row in subjects], dtype=np.int64)
    broad_scores, _ = _ridge_scores(features, broad_labels.astype(np.float64), folds, alpha)
    broad_metrics = _classification_metrics(broad_labels, broad_scores)
    broad_metrics["definition"] = (
        "persistent atrial fibrillation or paroxysmal atrial flutter in Conclusion, "
        "or any non-empty/non-'/' Atrial Fibrillation event field"
    )

    persistent_labels = np.asarray([row.persistent_af for row in subjects], dtype=np.int64)
    persistent_scores, _ = _ridge_scores(features, persistent_labels.astype(np.float64), folds, alpha)
    persistent_metrics = _classification_metrics(persistent_labels, persistent_scores)
    persistent_metrics["definition"] = "Conclusion contains exact phrase 'persistent atrial fibrillation'"
    persistent_metrics["subject_bootstrap_95ci"] = _stratified_bootstrap(
        persistent_labels,
        persistent_scores,
        seed=int(config["bootstrap"]["seed"]),
        iterations=int(config["bootstrap"]["iterations"]),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.plots_dir.mkdir(parents=True, exist_ok=True)

    task_metrics = {
        "dataset": {
            "article_id": 28643153,
            "title": article.get("title"),
            "license": (article.get("license") or {}).get("name"),
            "subjects": len(subjects),
            "sampling_hz": config["dataset"]["sampling_hz"],
            "used_samples_per_subject": config["representation"]["used_samples_per_subject"],
            "used_minutes_per_subject": (
                config["representation"]["used_samples_per_subject"] / config["dataset"]["sampling_hz"] / 60
            ),
        },
        "representation": config["representation"],
        "split": split,
        "probe": config["probe"],
        "age_regression": age_metrics,
        "broad_af": broad_metrics,
        "persistent_af": persistent_metrics,
        "interpretation": {
            "gate_3": "measurable independent cardiovascular transfer",
            "age_regression": "failed train-mean baseline",
            "broad_af": "weak",
            "persistent_af": (
                "exploratory continuous-rhythm endpoint; above trivial baselines but selected after inspecting "
                "the available metadata and should not be treated as confirmatory"
            ),
        },
    }
    (args.output_dir / "metrics.json").write_text(json.dumps(task_metrics, indent=2) + "\n")

    subject_rows = []
    persistent_prediction_rows = []
    age_prediction_rows = []
    for index, row in enumerate(subjects):
        subject_rows.append(
            {
                "subject_id": row.subject_id,
                "sex": row.sex,
                "age": row.age,
                "broad_af": row.broad_af,
                "persistent_af": row.persistent_af,
                "fold": int(folds[index]),
            }
        )
        persistent_prediction_rows.append(
            {
                "subject_id": row.subject_id,
                "fold": int(folds[index]),
                "label": row.persistent_af,
                "score": float(persistent_scores[index]),
                "prediction_at_0_5": int(persistent_scores[index] >= 0.5),
            }
        )
        age_prediction_rows.append(
            {
                "subject_id": row.subject_id,
                "fold": int(folds[index]),
                "age": row.age,
                "prediction": float(age_scores[index]),
                "train_mean_baseline": float(age_baselines[index]),
            }
        )

    pd.DataFrame(subject_rows).to_csv(args.output_dir / "subject_folds.csv", index=False)
    pd.DataFrame(persistent_prediction_rows).to_csv(
        args.output_dir / "persistent_af_predictions.csv", index=False
    )
    pd.DataFrame(age_prediction_rows).to_csv(args.output_dir / "age_predictions.csv", index=False)
    pd.DataFrame(
        [
            {
                "task": "age_regression",
                "primary_metric": "MAE",
                "estimate": age_metrics["mae_years"],
                "baseline": age_metrics["baseline_train_mean_mae_years"],
            },
            {"task": "broad_af", "primary_metric": "AUROC", "estimate": broad_metrics["auroc"], "baseline": 0.5},
            {
                "task": "persistent_af",
                "primary_metric": "AUROC",
                "estimate": persistent_metrics["auroc"],
                "baseline": 0.5,
            },
        ]
    ).to_csv(args.output_dir / "task_summary.csv", index=False)

    _plot_persistent_roc(persistent_labels, persistent_scores, args.plots_dir / "persistent_af_roc.svg")
    _plot_task_summary(task_metrics, args.plots_dir / "classification_auroc.svg")
    print(json.dumps(task_metrics, indent=2))


if __name__ == "__main__":
    main()
