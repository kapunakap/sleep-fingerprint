from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import requests
from scipy.io import loadmat
from scipy.signal import butter, correlate, detrend, find_peaks, resample_poly, sosfiltfilt, welch
from scipy.stats import kurtosis, pearsonr, skew
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .experiment import bootstrap_group_mean_ci, shuffled_label_control, summary
from .retrieval import l2_normalize

PLOS_DOI = "10.1371/journal.pone.0306074"
PLOS_LICENSE = "CC BY 4.0"
PLOS_SOURCE_FS_HZ = 2500.0
PLOS_TARGET_FS_HZ = 125.0
PLOS_SUBJECTS = tuple(range(1, 28))
PLOS_SUPPLEMENT_URL = (
    "https://journals.plos.org/plosone/article/file?type=supplementary&id="
    "10.1371/journal.pone.0306074.s{subject:03d}"
)
SENSOR_LABELS = (
    "S1_head_carotid",
    "S2_neck_aortic_arch",
    "S3_chest_heart_aorta",
    "S4_chest_heart_aorta",
    "S5_loins_renal_aorta",
    "S6_buttocks_iliac",
    "S7_buttocks_iliac",
    "S8_leg_femoral",
)
FEATURE_VARIANTS = (
    "normalized_spectrum",
    "cardiac_spectrum",
    "respiratory_spectrum",
    "morphology",
    "amplitude_bearing",
)


def supplement_url(subject: int) -> str:
    if subject not in PLOS_SUBJECTS:
        raise ValueError(f"unsupported PLOS subject: {subject}")
    return PLOS_SUPPLEMENT_URL.format(subject=subject)


def download_subject(subject: int, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest_md5 = hashlib.md5(usedforsecurity=False)
    digest_sha256 = hashlib.sha256()
    byte_count = 0
    with requests.get(
        supplement_url(subject),
        stream=True,
        timeout=(30, 180),
        headers={"User-Agent": "sleep-fingerprint-research/0.1"},
    ) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(8 * 1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                digest_md5.update(chunk)
                digest_sha256.update(chunk)
                byte_count += len(chunk)
    return {
        "subject_id": f"P{subject:02d}",
        "bytes": byte_count,
        "md5": digest_md5.hexdigest(),
        "sha256": digest_sha256.hexdigest(),
        "source_url": supplement_url(subject),
    }


def load_subject(path: Path) -> tuple[np.ndarray, np.ndarray]:
    payload = loadmat(path, squeeze_me=True, struct_as_record=False)
    bcg = np.asarray(payload["BCG"], dtype=np.float64)
    ecg = np.asarray(payload["ECG"], dtype=np.float64).reshape(-1)
    if bcg.ndim != 2 or bcg.shape[0] != len(SENSOR_LABELS):
        raise ValueError(f"expected 8-channel BCG, got {bcg.shape}")
    if bcg.shape[1] != ecg.size:
        raise ValueError("BCG and ECG lengths differ")
    if not np.all(np.isfinite(bcg)) or not np.all(np.isfinite(ecg)):
        raise ValueError("non-finite PLOS signal")
    return bcg, ecg


def temporal_blocks(sample_count: int, fs_hz: float = PLOS_SOURCE_FS_HZ) -> dict[str, tuple[int, int]]:
    margin = int(round(30 * fs_hz))
    if sample_count <= 2 * margin + int(6 * 60 * fs_hz):
        raise ValueError("recording too short for disjoint 3-block protocol")
    start = margin
    end = sample_count - margin
    block = (end - start) // 3
    ranges = {
        "enroll": (start, start + block),
        "middle": (start + block, start + 2 * block),
        "query": (start + 2 * block, end),
    }
    ordered = [ranges[name] for name in ("enroll", "middle", "query")]
    if any(a1 > b0 for (_, a1), (b0, _) in zip(ordered, ordered[1:], strict=True)):
        raise AssertionError("temporal blocks overlap")
    return ranges


def _robust_z(values: np.ndarray) -> np.ndarray:
    x = detrend(np.asarray(values, dtype=np.float64), type="linear")
    median = float(np.median(x))
    mad = float(np.median(np.abs(x - median)))
    scale = 1.4826 * mad
    if scale <= np.finfo(float).eps:
        scale = float(np.std(x))
    if scale <= np.finfo(float).eps:
        raise ValueError("flat signal")
    return (x - median) / scale


def _resample(values: np.ndarray, source_fs_hz: float, target_fs_hz: float = PLOS_TARGET_FS_HZ) -> np.ndarray:
    source = int(round(source_fs_hz))
    target = int(round(target_fs_hz))
    gcd = int(np.gcd(source, target))
    return resample_poly(np.asarray(values, dtype=np.float64), target // gcd, source // gcd, padtype="line")


def _band_power(frequencies: np.ndarray, power: np.ndarray, low: float, high: float) -> float:
    mask = (frequencies >= low) & (frequencies < high)
    if np.count_nonzero(mask) < 2:
        return 0.0
    return float(np.trapezoid(power[mask], frequencies[mask]))


def _spectrum_features(values: np.ndarray, fs_hz: float, low: float, high: float, bins: int) -> list[float]:
    frequencies, power = welch(values, fs=fs_hz, nperseg=min(len(values), int(round(8 * fs_hz))))
    mask = (frequencies >= low) & (frequencies <= high)
    frequencies = frequencies[mask]
    power = power[mask]
    if frequencies.size < 4:
        raise ValueError("insufficient spectral support")
    total = float(np.trapezoid(power, frequencies))
    power = power / max(total, np.finfo(float).tiny)
    edges = np.linspace(low, high, bins + 1)
    result = [np.log(_band_power(frequencies, power, edges[i], edges[i + 1]) + 1e-12) for i in range(bins)]
    peak = float(frequencies[int(np.argmax(power))])
    centroid = float(np.sum(frequencies * power) / max(np.sum(power), np.finfo(float).tiny))
    return [*result, peak, centroid]


def window_features(values: np.ndarray, fs_hz: float, variant: str) -> np.ndarray:
    raw = detrend(np.asarray(values, dtype=np.float64), type="linear")
    normalized = _robust_z(raw)
    if variant == "normalized_spectrum":
        result = _spectrum_features(normalized, fs_hz, 0.08, 15.0, 40)
    elif variant == "cardiac_spectrum":
        result = _spectrum_features(normalized, fs_hz, 0.7, 15.0, 36)
    elif variant == "respiratory_spectrum":
        result = _spectrum_features(normalized, fs_hz, 0.08, 0.7, 16)
    elif variant == "morphology":
        spectrum = _spectrum_features(normalized, fs_hz, 0.08, 15.0, 24)
        centered = normalized - float(np.mean(normalized))
        variance = float(np.dot(centered, centered))
        autocorr: list[float] = []
        for seconds in (0.2, 0.35, 0.5, 0.75, 1.0, 1.25):
            lag = int(round(seconds * fs_hz))
            numerator = float(np.dot(centered[:-lag], centered[lag:])) if lag < centered.size else 0.0
            autocorr.append(numerator / max(variance, np.finfo(float).tiny))
        result = [
            *spectrum,
            float(skew(normalized, bias=False)),
            float(kurtosis(normalized, fisher=True, bias=False)),
            float(np.mean(np.abs(np.diff(normalized)))),
            *autocorr,
        ]
    elif variant == "amplitude_bearing":
        frequencies, power = welch(raw, fs=fs_hz, nperseg=min(len(raw), int(round(8 * fs_hz))))
        bands = ((0.08, 0.7), (0.7, 1.5), (1.5, 3.0), (3.0, 6.0), (6.0, 10.0), (10.0, 15.0))
        amplitude = [
            np.log(float(np.std(raw)) + 1e-12),
            np.log(float(np.sqrt(np.mean(np.square(raw)))) + 1e-12),
            np.log(float(np.median(np.abs(raw - np.median(raw)))) + 1e-12),
            np.log(float(np.percentile(raw, 95) - np.percentile(raw, 5)) + 1e-12),
        ]
        absolute_band_power = [np.log(_band_power(frequencies, power, low, high) + 1e-12) for low, high in bands]
        result = [*amplitude, *absolute_band_power, *_spectrum_features(normalized, fs_hz, 0.08, 15.0, 24)]
    else:
        raise ValueError(f"unknown feature variant: {variant}")
    return np.nan_to_num(np.asarray(result, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)


def block_feature(
    values: np.ndarray,
    source_fs_hz: float,
    interval: tuple[int, int],
    variant: str,
    *,
    window_seconds: float = 30.0,
) -> np.ndarray:
    start, end = interval
    segment = _resample(values[start:end], source_fs_hz)
    window = int(round(window_seconds * PLOS_TARGET_FS_HZ))
    features: list[np.ndarray] = []
    for offset in range(0, segment.size - window + 1, window):
        piece = segment[offset : offset + window]
        try:
            features.append(window_features(piece, PLOS_TARGET_FS_HZ, variant))
        except ValueError:
            continue
    if len(features) < 3:
        raise ValueError("fewer than three usable windows in temporal block")
    return np.median(np.stack(features), axis=0)


def subject_features(bcg: np.ndarray) -> dict[str, dict[str, list[np.ndarray]]]:
    ranges = temporal_blocks(bcg.shape[1])
    result: dict[str, dict[str, list[np.ndarray]]] = {}
    for variant in FEATURE_VARIANTS:
        result[variant] = {}
        for block_name, interval in ranges.items():
            result[variant][block_name] = [
                block_feature(bcg[sensor], PLOS_SOURCE_FS_HZ, interval, variant)
                for sensor in range(len(SENSOR_LABELS))
            ]
    return result


def _pair_similarity(
    features: dict[str, dict[str, dict[str, list[np.ndarray]]]],
    variant: str,
    enroll_sensor: int,
    query_sensor: int,
    *,
    query_block: str = "query",
) -> tuple[list[str], np.ndarray]:
    subjects = sorted(features)
    enroll = np.stack([features[subject][variant]["enroll"][enroll_sensor] for subject in subjects])
    query = np.stack([features[subject][variant][query_block][query_sensor] for subject in subjects])
    scaler = StandardScaler().fit(enroll)
    gallery = l2_normalize(scaler.transform(enroll))
    probes = l2_normalize(scaler.transform(query))
    return subjects, probes @ gallery.T


def _metrics_from_matrices(
    matrices: list[tuple[int, int, list[str], np.ndarray]],
    *,
    bootstrap_repetitions: int = 2000,
    seed: int = 20260905,
) -> dict[str, Any]:
    if not matrices:
        raise ValueError("no pair matrices")
    cohort = matrices[0][3].shape[0]
    rank1_by_subject: dict[str, list[float]] = defaultdict(list)
    rank5_by_subject: dict[str, list[float]] = defaultdict(list)
    same: list[float] = []
    different: list[float] = []
    y_true: list[int] = []
    y_score: list[float] = []
    confusion = np.zeros((cohort, cohort), dtype=int)
    pair_rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    similarity_only: list[np.ndarray] = []
    for enroll_sensor, query_sensor, subjects, matrix in matrices:
        similarity_only.append(matrix)
        order = np.argsort(-matrix, axis=1, kind="stable")
        ranks: list[int] = []
        for query_index, subject in enumerate(subjects):
            rank = int(np.flatnonzero(order[query_index] == query_index)[0]) + 1
            ranks.append(rank)
            rank1_by_subject[subject].append(float(rank == 1))
            rank5_by_subject[subject].append(float(rank <= min(5, cohort)))
            confusion[query_index, int(order[query_index, 0])] += 1
            same.append(float(matrix[query_index, query_index]))
            for gallery_index, score in enumerate(matrix[query_index]):
                is_same = int(gallery_index == query_index)
                y_true.append(is_same)
                y_score.append(float(score))
                if not is_same:
                    different.append(float(score))
            query_rows.append(
                {
                    "subject_id": subject,
                    "enroll_sensor": SENSOR_LABELS[enroll_sensor],
                    "query_sensor": SENSOR_LABELS[query_sensor],
                    "rank": rank,
                    "same_person_similarity": float(matrix[query_index, query_index]),
                }
            )
        pair_rows.append(
            {
                "enroll_sensor": SENSOR_LABELS[enroll_sensor],
                "query_sensor": SENSOR_LABELS[query_sensor],
                "rank_1": float(np.mean(np.asarray(ranks) == 1)),
                "rank_5": float(np.mean(np.asarray(ranks) <= min(5, cohort))),
                "median_rank": float(np.median(ranks)),
                "verification_auroc": float(
                    roc_auc_score(
                        np.eye(cohort, dtype=int).ravel(),
                        matrix.ravel(),
                    )
                ),
            }
        )
    rank1_ci = bootstrap_group_mean_ci(rank1_by_subject, repetitions=bootstrap_repetitions, seed=seed)
    rank5_ci = bootstrap_group_mean_ci(rank5_by_subject, repetitions=bootstrap_repetitions, seed=seed + 1)
    per_participant = {
        subject: {
            "queries": len(rank1_by_subject[subject]),
            "rank_1": float(np.mean(rank1_by_subject[subject])),
            "rank_5": float(np.mean(rank5_by_subject[subject])),
        }
        for subject in sorted(rank1_by_subject)
    }
    return {
        "cohort_size": cohort,
        "query_count": len(query_rows),
        "sensor_pair_count": len(matrices),
        "chance_rank_1": float(1 / cohort),
        "rank_1": rank1_ci,
        "rank_5": rank5_ci,
        "verification_auroc": float(roc_auc_score(y_true, y_score)),
        "same_person_similarity": summary(same),
        "different_person_similarity": summary(different),
        "confusion_matrix": confusion.tolist(),
        "per_participant": per_participant,
        "pair_metrics": pair_rows,
        "queries": query_rows,
        "shuffled_labels": shuffled_label_control(similarity_only, repetitions=500, seed=seed + 2),
    }


def cross_sensor_retrieval(
    features: dict[str, dict[str, dict[str, list[np.ndarray]]]],
    variant: str,
    *,
    query_block: str = "query",
    bootstrap_repetitions: int = 2000,
) -> dict[str, Any]:
    matrices: list[tuple[int, int, list[str], np.ndarray]] = []
    for enroll_sensor in range(len(SENSOR_LABELS)):
        for query_sensor in range(len(SENSOR_LABELS)):
            if enroll_sensor == query_sensor:
                continue
            subjects, matrix = _pair_similarity(
                features, variant, enroll_sensor, query_sensor, query_block=query_block
            )
            matrices.append((enroll_sensor, query_sensor, subjects, matrix))
    metrics = _metrics_from_matrices(matrices, bootstrap_repetitions=bootstrap_repetitions)
    subjects, matrix = _pair_similarity(features, variant, 3, 6, query_block=query_block)
    metrics["predeclared_s4_to_s7"] = _metrics_from_matrices(
        [(3, 6, subjects, matrix)], bootstrap_repetitions=bootstrap_repetitions, seed=20260917
    )
    return metrics


def setup_prediction(
    features: dict[str, dict[str, dict[str, list[np.ndarray]]]],
    variant: str,
) -> dict[str, Any]:
    subjects = sorted(features)
    x: list[np.ndarray] = []
    y: list[int] = []
    groups: list[str] = []
    for subject in subjects:
        for sensor in range(len(SENSOR_LABELS)):
            x.append(features[subject][variant]["middle"][sensor])
            y.append(sensor)
            groups.append(subject)
    matrix = np.stack(x)
    labels = np.asarray(y, dtype=int)
    group_array = np.asarray(groups)
    predictions = np.full(labels.shape, -1, dtype=int)
    splitter = GroupKFold(n_splits=5)
    for train_index, test_index in splitter.split(matrix, labels, groups=group_array):
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=5000, solver="lbfgs"),
        )
        model.fit(matrix[train_index], labels[train_index])
        predictions[test_index] = model.predict(matrix[test_index])
    if np.any(predictions < 0):
        raise AssertionError("participant-safe setup prediction left unpredicted samples")
    return {
        "samples": int(labels.size),
        "subjects": int(len(subjects)),
        "classes": int(len(SENSOR_LABELS)),
        "chance_accuracy": float(1 / len(SENSOR_LABELS)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(f1_score(labels, predictions, average="macro")),
        "split": "5-fold GroupKFold grouped by participant",
    }


def _sos_bandpass(values: np.ndarray, fs_hz: float, low: float, high: float, order: int = 4) -> np.ndarray:
    sos = butter(order, (low, high), btype="bandpass", fs=fs_hz, output="sos")
    return sosfiltfilt(sos, detrend(np.asarray(values, dtype=np.float64), type="linear"))


def estimate_ecg_bpm(values: np.ndarray, source_fs_hz: float = PLOS_SOURCE_FS_HZ) -> float | None:
    sampled = _resample(values, source_fs_hz, 250.0)
    filtered = _sos_bandpass(sampled, 250.0, 5.0, 35.0)
    candidates: list[tuple[float, float]] = []
    for sign in (1.0, -1.0):
        oriented = sign * filtered
        peaks, _ = find_peaks(
            oriented,
            distance=int(round(0.28 * 250)),
            prominence=max(float(np.std(oriented)) * 0.55, np.finfo(float).eps),
        )
        if peaks.size < 10:
            continue
        rr = np.diff(peaks) / 250.0
        rr = rr[(rr >= 0.3) & (rr <= 1.7)]
        if rr.size < 8:
            continue
        bpm = float(60.0 / np.median(rr))
        if not 35 <= bpm <= 200:
            continue
        regularity = float(np.std(rr) / max(np.mean(rr), np.finfo(float).eps))
        candidates.append((regularity, bpm))
    return min(candidates)[1] if candidates else None


def estimate_bcg_spectral_bpm(values: np.ndarray, source_fs_hz: float = PLOS_SOURCE_FS_HZ) -> float | None:
    sampled = _resample(values, source_fs_hz, PLOS_TARGET_FS_HZ)
    normalized = _robust_z(sampled)
    frequencies, power = welch(
        normalized,
        fs=PLOS_TARGET_FS_HZ,
        nperseg=min(len(normalized), int(round(16 * PLOS_TARGET_FS_HZ))),
    )
    mask = (frequencies >= 0.7) & (frequencies <= 3.0)
    if np.count_nonzero(mask) < 2:
        return None
    candidates = frequencies[mask]
    candidate_power = power[mask]
    return float(candidates[int(np.argmax(candidate_power))] * 60.0)


def estimate_bcg_autocorr_bpm(values: np.ndarray, source_fs_hz: float = PLOS_SOURCE_FS_HZ) -> float | None:
    sampled = _resample(values, source_fs_hz, PLOS_TARGET_FS_HZ)
    normalized = _robust_z(sampled)
    filtered = _sos_bandpass(normalized, PLOS_TARGET_FS_HZ, 0.7, 10.0)
    corr = correlate(filtered, filtered, mode="full", method="fft")[filtered.size - 1 :]
    low_lag = int(round(PLOS_TARGET_FS_HZ * 0.33))
    high_lag = int(round(PLOS_TARGET_FS_HZ * 1.5))
    if high_lag >= corr.size:
        return None
    lag = low_lag + int(np.argmax(corr[low_lag : high_lag + 1]))
    bpm = float(60.0 * PLOS_TARGET_FS_HZ / lag)
    return bpm if 35 <= bpm <= 200 else None


def physiology_window_records(
    subject_id: str,
    bcg: np.ndarray,
    ecg: np.ndarray,
) -> list[dict[str, Any]]:
    middle_start, middle_end = temporal_blocks(ecg.size)["middle"]
    window = int(round(60 * PLOS_SOURCE_FS_HZ))
    center = (middle_start + middle_end) // 2
    start = max(middle_start, center - window // 2)
    end = start + window
    if end > middle_end:
        end = middle_end
        start = end - window
    reference = estimate_ecg_bpm(ecg[start:end])
    if reference is None:
        return []
    rows: list[dict[str, Any]] = []
    for sensor, label in enumerate(SENSOR_LABELS):
        spectral = estimate_bcg_spectral_bpm(bcg[sensor, start:end])
        autocorr = estimate_bcg_autocorr_bpm(bcg[sensor, start:end])
        rows.append(
            {
                "subject_id": subject_id,
                "sensor": label,
                "ecg_bpm": reference,
                "spectral_bpm": spectral,
                "autocorr_bpm": autocorr,
            }
        )
    return rows


def physiology_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for method in ("spectral_bpm", "autocorr_bpm"):
        valid = [row for row in rows if row.get(method) is not None]
        reference = np.asarray([float(row["ecg_bpm"]) for row in valid])
        estimate = np.asarray([float(row[method]) for row in valid])
        if reference.size < 3:
            result[method] = {"windows": int(reference.size), "mae_bpm": None, "pearson_r": None}
            continue
        result[method] = {
            "windows": int(reference.size),
            "mae_bpm": float(np.mean(np.abs(estimate - reference))),
            "median_ae_bpm": float(np.median(np.abs(estimate - reference))),
            "pearson_r": float(pearsonr(reference, estimate).statistic),
        }
        by_sensor: dict[str, Any] = {}
        for sensor in SENSOR_LABELS:
            sensor_rows = [row for row in valid if row["sensor"] == sensor]
            sensor_ref = np.asarray([float(row["ecg_bpm"]) for row in sensor_rows])
            sensor_est = np.asarray([float(row[method]) for row in sensor_rows])
            by_sensor[sensor] = {
                "windows": int(sensor_ref.size),
                "mae_bpm": float(np.mean(np.abs(sensor_est - sensor_ref))) if sensor_ref.size else None,
                "pearson_r": float(pearsonr(sensor_ref, sensor_est).statistic) if sensor_ref.size >= 3 else None,
            }
        result[method]["by_sensor"] = by_sensor
    return result


def normalized_edge_signature(values: np.ndarray, source_fs_hz: float = PLOS_SOURCE_FS_HZ) -> str:
    sampled = _resample(values, source_fs_hz, 64.0)
    normalized = _robust_z(sampled)
    rounded = np.round(normalized, decimals=4).astype("<f4", copy=False)
    return hashlib.sha256(rounded.tobytes()).hexdigest()


def duplicate_signature_audit(
    subject_id: str,
    bcg: np.ndarray,
) -> list[dict[str, str]]:
    ranges = temporal_blocks(bcg.shape[1])
    seconds = int(round(10 * PLOS_SOURCE_FS_HZ))
    rows: list[dict[str, str]] = []
    for block_name in ("enroll", "query"):
        start, end = ranges[block_name]
        for sensor, label in enumerate(SENSOR_LABELS):
            left = bcg[sensor, start : start + seconds]
            right = bcg[sensor, end - seconds : end]
            rows.append(
                {
                    "subject_id": subject_id,
                    "sensor": label,
                    "block": block_name,
                    "edge": "left",
                    "signature": normalized_edge_signature(left),
                }
            )
            rows.append(
                {
                    "subject_id": subject_id,
                    "sensor": label,
                    "block": block_name,
                    "edge": "right",
                    "signature": normalized_edge_signature(right),
                }
            )
    return rows


def signature_collisions(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["signature"]].append(row)
    return [items for items in grouped.values() if len(items) > 1]
