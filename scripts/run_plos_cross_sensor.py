from __future__ import annotations

import csv
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from sleep_fingerprint.plos_multichannel import (
    FEATURE_VARIANTS,
    PLOS_DOI,
    PLOS_LICENSE,
    PLOS_SOURCE_FS_HZ,
    PLOS_SUBJECTS,
    PLOS_TARGET_FS_HZ,
    SENSOR_LABELS,
    _resample,
    cross_sensor_retrieval,
    download_subject,
    duplicate_signature_audit,
    load_subject,
    physiology_summary,
    physiology_window_records,
    setup_prediction,
    signature_collisions,
    temporal_blocks,
    window_features,
)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".research-cache" / "plos_multichannel"
OUT = ROOT / "metrics" / "plos_cross_sensor"
PLOTS = ROOT / "plots" / "plos_cross_sensor"


def _fast_subject_features(bcg: np.ndarray) -> dict[str, dict[str, list[np.ndarray]]]:
    result: dict[str, dict[str, list[np.ndarray]]] = {
        variant: {block: [np.empty(0) for _ in SENSOR_LABELS] for block in ("enroll", "middle", "query")}
        for variant in FEATURE_VARIANTS
    }
    ranges = temporal_blocks(bcg.shape[1])
    window = int(round(30 * PLOS_TARGET_FS_HZ))
    for block_name, (start, end) in ranges.items():
        for sensor in range(len(SENSOR_LABELS)):
            segment = _resample(bcg[sensor, start:end], PLOS_SOURCE_FS_HZ, PLOS_TARGET_FS_HZ)
            per_variant: dict[str, list[np.ndarray]] = {variant: [] for variant in FEATURE_VARIANTS}
            for offset in range(0, segment.size - window + 1, window):
                piece = segment[offset : offset + window]
                for variant in FEATURE_VARIANTS:
                    try:
                        per_variant[variant].append(window_features(piece, PLOS_TARGET_FS_HZ, variant))
                    except ValueError:
                        continue
            for variant in FEATURE_VARIANTS:
                if len(per_variant[variant]) < 3:
                    raise ValueError(
                        f"{block_name} sensor={sensor} variant={variant} has fewer than three usable windows"
                    )
                result[variant][block_name][sensor] = np.median(np.stack(per_variant[variant]), axis=0)
    return result


def _download_with_retry(subject: int, path: Path) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return download_subject(subject, path)
        except Exception as error:  # noqa: BLE001 - research download retry boundary
            last_error = error
            if path.exists():
                path.unlink()
            if attempt < 3:
                time.sleep(2**attempt)
    raise RuntimeError(f"failed to download PLOS subject {subject}") from last_error


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    columns = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _plot_pair_heatmap(pair_rows: list[dict[str, Any]]) -> None:
    matrix = np.full((len(SENSOR_LABELS), len(SENSOR_LABELS)), np.nan)
    index = {label: position for position, label in enumerate(SENSOR_LABELS)}
    for row in pair_rows:
        matrix[index[str(row["enroll_sensor"])], index[str(row["query_sensor"])]] = float(row["rank_1"])
    figure, axis = plt.subplots(figsize=(9, 7))
    image = axis.imshow(matrix, vmin=0, vmax=1)
    axis.set_xticks(range(len(SENSOR_LABELS)), [f"S{i}" for i in range(1, 9)])
    axis.set_yticks(range(len(SENSOR_LABELS)), [f"S{i}" for i in range(1, 9)])
    axis.set_xlabel("Query sensor/location")
    axis.set_ylabel("Enrollment sensor/location")
    axis.set_title("Disjoint-time cross-sensor Rank-1 accuracy")
    figure.colorbar(image, ax=axis, label="Rank-1")
    figure.tight_layout()
    figure.savefig(PLOTS / "cross_sensor_rank1.svg")
    plt.close(figure)


def _plot_setup_prediction(rows: list[dict[str, Any]]) -> None:
    figure, axis = plt.subplots(figsize=(9, 5))
    variants = [str(row["variant"]) for row in rows]
    accuracy = [float(row["accuracy"]) for row in rows]
    axis.bar(range(len(rows)), accuracy)
    axis.axhline(1 / len(SENSOR_LABELS), linestyle="--", label="chance")
    axis.set_xticks(range(len(rows)), variants, rotation=25, ha="right")
    axis.set_ylim(0, 1)
    axis.set_ylabel("Participant-safe sensor-location accuracy")
    axis.set_title("Can BCG features predict physical sensor location?")
    axis.legend()
    figure.tight_layout()
    figure.savefig(PLOTS / "setup_prediction.svg")
    plt.close(figure)


def _plot_physiology(rows: list[dict[str, Any]]) -> None:
    valid = [row for row in rows if row.get("spectral_bpm") is not None]
    if not valid:
        return
    reference = np.asarray([float(row["ecg_bpm"]) for row in valid])
    estimate = np.asarray([float(row["spectral_bpm"]) for row in valid])
    figure, axis = plt.subplots(figsize=(6, 6))
    axis.scatter(reference, estimate, alpha=0.65, s=18)
    low = float(min(np.min(reference), np.min(estimate)))
    high = float(max(np.max(reference), np.max(estimate)))
    axis.plot([low, high], [low, high], linestyle="--")
    axis.set_xlabel("ECG reference heart rate (bpm)")
    axis.set_ylabel("BCG spectral heart rate (bpm)")
    axis.set_title("Physiology check across eight BCG locations")
    figure.tight_layout()
    figure.savefig(PLOTS / "bcg_vs_ecg_hr.svg")
    plt.close(figure)


def _plos_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for subject in PLOS_SUBJECTS:
        participant = f"P{subject:02d}"
        for sensor_index, sensor_position in enumerate(SENSOR_LABELS, start=1):
            rows.append(
                {
                    "participant_id": participant,
                    "participant_id_provenance": "PLOS supplement number s001-s027; paper maps one file to one proband",
                    "night_id": None,
                    "session_id": f"s{subject:03d}",
                    "session_id_provenance": "source supplement file identity; not an installation identifier",
                    "bed_id": None,
                    "mattress_id": None,
                    "sensor_id": f"S{sensor_index}",
                    "sensor_id_provenance": "paper-defined simultaneous BCG channel label",
                    "device_id": None,
                    "installation_id": None,
                    "installation_id_provenance": "unknown; source does not define removal/reinstallation boundaries",
                    "sensor_position": sensor_position,
                    "sensor_position_provenance": "paper-defined physical sensor location",
                    "recording_location": None,
                    "dataset_id": f"doi:{PLOS_DOI}",
                    "recording_date": None,
                }
            )
    return rows


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)
    features: dict[str, dict[str, dict[str, list[np.ndarray]]]] = {}
    physiology_rows: list[dict[str, Any]] = []
    signature_rows: list[dict[str, str]] = []
    downloads: list[dict[str, Any]] = []
    durations: dict[str, float] = {}

    for subject in PLOS_SUBJECTS:
        subject_id = f"P{subject:02d}"
        path = CACHE / f"pone.0306074.s{subject:03d}.mat"
        metadata = _download_with_retry(subject, path)
        bcg, ecg = load_subject(path)
        durations[subject_id] = float(ecg.size / PLOS_SOURCE_FS_HZ)
        print(subject_id, "shape", bcg.shape, "duration_s", durations[subject_id], flush=True)
        features[subject_id] = _fast_subject_features(bcg)
        physiology_rows.extend(physiology_window_records(subject_id, bcg, ecg))
        signature_rows.extend(duplicate_signature_audit(subject_id, bcg))
        downloads.append(metadata)
        path.unlink()

    feature_results: dict[str, Any] = {}
    setup_rows: list[dict[str, Any]] = []
    for variant in FEATURE_VARIANTS:
        disjoint = cross_sensor_retrieval(features, variant, query_block="query")
        setup = setup_prediction(features, variant)
        setup_rows.append({"variant": variant, **setup})
        feature_results[variant] = {"disjoint_cross_sensor": disjoint, "setup_prediction": setup}
        print(
            variant,
            "rank1",
            disjoint["rank_1"]["estimate"],
            "rank5",
            disjoint["rank_5"]["estimate"],
            "auc",
            disjoint["verification_auroc"],
            "setup_accuracy",
            setup["accuracy"],
            flush=True,
        )

    same_time = cross_sensor_retrieval(features, "normalized_spectrum", query_block="enroll")
    physiology = physiology_summary(physiology_rows)
    collisions = signature_collisions(signature_rows)
    manifest = _plos_manifest()
    metric_payload = {
        "dataset": {
            "title": "Multichannel ballistocardiography: A comparative analysis of heartbeat detection across different body locations",
            "doi": PLOS_DOI,
            "license": PLOS_LICENSE,
            "participants": len(PLOS_SUBJECTS),
            "physical_bcg_channels": len(SENSOR_LABELS),
            "source_sampling_hz": PLOS_SOURCE_FS_HZ,
            "download_count": len(downloads),
            "download_checksums": downloads,
            "duration_seconds": {
                "min": min(durations.values()),
                "median": float(np.median(list(durations.values()))),
                "max": max(durations.values()),
            },
        },
        "protocol": {
            "interpretation": "same-session cross-sensor/cross-location proxy; not cross-night and not reinstallation",
            "temporal_split": "30 s margins; remaining recording split into three contiguous thirds; enrollment=first third, query=last third",
            "window_seconds": 30,
            "feature_scaling": "StandardScaler fit on enrollment vectors only, followed by L2 normalization",
            "sensor_pairs": "all 56 directed off-diagonal sensor-location pairs; S4->S7 predeclared far-location pair reported separately",
            "chance_rank_1": 1 / len(PLOS_SUBJECTS),
        },
        "features": feature_results,
        "same_time_cross_sensor_control": same_time,
        "physiology_validation": physiology,
        "duplicate_resampled_edge_signatures": {
            "signatures": len(signature_rows),
            "collisions": len(collisions),
            "collision_examples": collisions[:10],
        },
    }
    (OUT / "metrics.json").write_text(json.dumps(metric_payload, indent=2) + "\n")
    _write_csv(OUT / "manifest.csv", manifest)
    _write_csv(OUT / "downloads.csv", downloads)
    _write_csv(OUT / "physiology_windows.csv", physiology_rows)
    _write_csv(OUT / "setup_prediction.csv", setup_rows)
    _write_csv(OUT / "edge_signatures.csv", signature_rows)

    normalized = feature_results["normalized_spectrum"]["disjoint_cross_sensor"]
    _write_csv(OUT / "pair_metrics_normalized_spectrum.csv", normalized["pair_metrics"])
    _write_csv(
        OUT / "per_participant_normalized_spectrum.csv",
        [
            {"participant_id": participant, **values}
            for participant, values in normalized["per_participant"].items()
        ],
    )
    _write_csv(OUT / "queries_normalized_spectrum.csv", normalized["queries"])
    _plot_pair_heatmap(normalized["pair_metrics"])
    _plot_setup_prediction(setup_rows)
    _plot_physiology(physiology_rows)

    print("duplicate_signature_collisions", len(collisions))
    print("manifest_rows", len(manifest))
    print("result_files", sorted(path.as_posix() for path in OUT.iterdir()))
    print("plot_files", sorted(path.as_posix() for path in PLOTS.iterdir()))
    print("sensor_counts", Counter(row["sensor_id"] for row in manifest))


if __name__ == "__main__":
    main()
