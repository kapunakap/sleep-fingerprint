from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sleep_fingerprint.dataset import (
    EXPECTED_ARCHIVE_BYTES,
    EXPECTED_ARCHIVE_MD5,
    audit_dataset,
    download_dataset,
    safe_extract_zip,
)
from sleep_fingerprint.primary_experiment import (
    add_reference_physiology,
    duplicate_signature_collisions,
    evaluate_feature_variant,
    evaluate_scalar_shortcut,
    extract_primary_night_features,
    installation_aware_primary_manifest,
    make_chronological_half_split,
    physiology_metrics,
    shuffled_label_control,
    summarize_split,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / ".research-cache" / "primary_figshare_26013157"
EXTRACTED = DATA_DIR / "extracted"
OUT = ROOT / "metrics" / "primary_cross_night"
PLOTS = ROOT / "plots" / "primary_cross_night"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _plot_confusion(matrix: list[list[int]], labels: list[str]) -> None:
    values = np.asarray(matrix, dtype=float)
    figure, axis = plt.subplots(figsize=(10, 9))
    image = axis.imshow(values)
    axis.set_xlabel("Predicted participant")
    axis.set_ylabel("True participant")
    axis.set_title("Primary cross-night test confusion matrix")
    ticks = np.arange(len(labels))
    short = [str(label) for label in labels]
    axis.set_xticks(ticks, short, rotation=90, fontsize=6)
    axis.set_yticks(ticks, short, fontsize=6)
    figure.colorbar(image, ax=axis, label="Query nights")
    figure.tight_layout()
    figure.savefig(PLOTS / "test_confusion.svg")
    plt.close(figure)


def _plot_ablation(rows: list[dict[str, Any]]) -> None:
    figure, axis = plt.subplots(figsize=(10, 6))
    names = [str(row["variant"]) for row in rows]
    rank1 = [float(row["test_rank_1"]) for row in rows]
    axis.bar(range(len(rows)), rank1)
    axis.axhline(1 / 32, linestyle="--", label="chance")
    axis.set_xticks(range(len(rows)), names, rotation=28, ha="right")
    axis.set_ylabel("Test Rank-1")
    axis.set_ylim(0, max(0.35, max(rank1) * 1.15))
    axis.set_title("Primary cross-night ablations")
    axis.legend()
    figure.tight_layout()
    figure.savefig(PLOTS / "ablation_rank1.svg")
    plt.close(figure)


def _plot_similarity_summary(primary: dict[str, Any]) -> None:
    same = primary["test"]["same_person_similarity"]
    different = primary["test"]["different_person_similarity"]
    labels = ["same person", "different person"]
    means = [float(same["mean"]), float(different["mean"])]
    figure, axis = plt.subplots(figsize=(6, 5))
    axis.bar(range(2), means)
    axis.set_xticks(range(2), labels)
    axis.set_ylabel("Cosine similarity")
    axis.set_title("Primary cross-night similarity means")
    figure.tight_layout()
    figure.savefig(PLOTS / "similarity_means.svg")
    plt.close(figure)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    archive, verification = download_dataset(DATA_DIR)
    extraction = safe_extract_zip(archive, EXTRACTED)
    records, audit, bad = audit_dataset(EXTRACTED)
    manifest = [asdict(record) for record in records]
    if len(records) != 212 or audit["subjects"] != 32:
        raise RuntimeError(f"primary dataset identity mismatch after extraction: {audit}")
    if bad:
        raise RuntimeError(f"primary dataset contains invalid BCG records: {bad[:3]}")

    night_counts = Counter(record.subject_id for record in records)
    split = make_chronological_half_split(manifest)
    split_summary = summarize_split(split)
    features, physiology_rows = extract_primary_night_features(manifest, EXTRACTED)
    accepted_nights = {str(row["night_key"]) for row in features}
    if len(accepted_nights) != len(records):
        missing = sorted(record.night_key for record in records if record.night_key not in accepted_nights)
        raise RuntimeError(f"BCG QC removed complete nights: {missing}")

    variant_specs = {
        "combined_normalized": ("combined_normalized", None),
        "cardiac_only": ("cardiac_only", None),
        "respiratory_only": ("respiratory_only", None),
        "phase_insensitive_spectral": ("phase_insensitive_spectral", None),
        "morphology_heavy": ("morphology_heavy", None),
        "amplitude_bearing": ("amplitude_bearing", None),
        "random_temporal_half": ("combined_random_half", None),
        "early_to_late": ("combined_early", "combined_late"),
        "late_to_early": ("combined_late", "combined_early"),
    }
    variants: dict[str, Any] = {}
    ablation_rows: list[dict[str, Any]] = []
    for name, (train_feature, query_feature) in variant_specs.items():
        result = evaluate_feature_variant(
            features,
            split,
            train_feature=train_feature,
            query_feature=query_feature,
        )
        variants[name] = result
        ablation_rows.append(
            {
                "variant": name,
                "val_rank_1": result["val"]["rank_1"]["estimate"],
                "val_rank_5": result["val"]["rank_5"]["estimate"],
                "test_rank_1": result["test"]["rank_1"]["estimate"],
                "test_rank_5": result["test"]["rank_5"]["estimate"],
                "test_auroc": result["test"]["verification_auroc"],
            }
        )
        print(
            name,
            "val",
            result["val"]["rank_1"]["estimate"],
            result["val"]["rank_5"]["estimate"],
            "test",
            result["test"]["rank_1"]["estimate"],
            result["test"]["rank_5"]["estimate"],
            flush=True,
        )

    shuffled = shuffled_label_control(features, split)
    shortcut_controls = {
        "duration_seconds": evaluate_scalar_shortcut(features, split, value_field="duration_seconds"),
        "start_hour": evaluate_scalar_shortcut(features, split, value_field="start_hour"),
    }
    collisions = duplicate_signature_collisions(features)
    physiology_rows = add_reference_physiology(physiology_rows, manifest, EXTRACTED)
    physiology = physiology_metrics(physiology_rows)
    installation_manifest = installation_aware_primary_manifest(records)

    primary = variants["combined_normalized"]
    expected_reproduction = {
        "expected_validation_queries": 64,
        "expected_validation_rank_1": 0.25,
        "expected_validation_rank_5": 0.53125,
        "expected_test_queries": 54,
        "expected_test_rank_1": 14 / 54,
        "expected_test_rank_5": 0.5,
        "query_counts_match": (
            primary["val"]["query_count"] == 64 and primary["test"]["query_count"] == 54
        ),
        "metrics_match_to_1e_12": (
            abs(float(primary["val"]["rank_1"]["estimate"]) - 0.25) < 1e-12
            and abs(float(primary["val"]["rank_5"]["estimate"]) - 0.53125) < 1e-12
            and abs(float(primary["test"]["rank_1"]["estimate"]) - 14 / 54) < 1e-12
            and abs(float(primary["test"]["rank_5"]["estimate"]) - 0.5) < 1e-12
        ),
    }
    payload = {
        "dataset": {
            "article_id": 26013157,
            "file_id": 46976602,
            "archive_bytes": EXPECTED_ARCHIVE_BYTES,
            "archive_md5": EXPECTED_ARCHIVE_MD5,
            "verification": verification,
            "extraction": extraction,
            "license": "CC BY 4.0",
            "audit": audit,
            "nights_per_participant_distribution": dict(sorted(Counter(night_counts.values()).items())),
            "reference_rr_nights": int(sum(record.has_reference_rr for record in records)),
            "reference_resp_nights": int(sum(record.has_reference_resp for record in records)),
        },
        "protocol": {
            "split": (
                "per participant, chronological first floor(n/2) nights enroll/train; remaining nights split "
                "chronologically with ceil(heldout/2) validation and the rest test"
            ),
            "split_summary": split_summary,
            "preprocessing": "140 Hz -> 64 Hz; 60 s windows, 30 s stride; QC; per-window robust z; respiratory 0.08-0.7 Hz; cardiac 0.7-15 Hz",
            "night_embedding": "up to 12 evenly spaced accepted windows; median handcrafted features; StandardScaler fit on train nights only; L2 cosine retrieval",
            "installation_interpretation": (
                "night_id is not installation_id; bed/mattress/sensor/device/installation identity unknown"
            ),
        },
        "reproduction_of_prior_control": expected_reproduction,
        "variants": variants,
        "negative_controls": {
            "shuffled_participant_labels": shuffled,
            "scalar_shortcuts": shortcut_controls,
            "edge_signature_count": len(features) * 2,
            "duplicate_or_resampled_edge_collisions": collisions,
        },
        "physiology_validation": physiology,
    }
    (OUT / "metrics.json").write_text(json.dumps(payload, indent=2) + "\n")
    _write_csv(OUT / "manifest_installation_aware.csv", installation_manifest)
    _write_csv(
        OUT / "split_assignments.csv",
        [
            {
                "subject_id": assignment.subject_id,
                "night_key": assignment.night_key,
                "split": assignment.split,
                "source_path": assignment.source_path,
            }
            for assignment in split.assignments
        ],
    )
    _write_csv(
        OUT / "night_qc.csv",
        [
            {
                key: value
                for key, value in row.items()
                if key not in {"features", "left_edge_signature", "right_edge_signature"}
            }
            for row in features
        ],
    )
    _write_csv(OUT / "physiology_nights.csv", physiology_rows)
    _write_csv(OUT / "ablation_summary.csv", ablation_rows)
    _write_csv(
        OUT / "per_participant_test.csv",
        [
            {"participant_id": participant, **metrics}
            for participant, metrics in primary["test"]["per_participant"].items()
        ],
    )
    pd.DataFrame(primary["test"]["confusion_matrix"], index=primary["test"]["labels"], columns=primary["test"]["labels"]).to_csv(
        OUT / "test_confusion.csv"
    )
    _plot_confusion(primary["test"]["confusion_matrix"], primary["test"]["labels"])
    _plot_ablation(ablation_rows)
    _plot_similarity_summary(primary)

    print("audit", audit)
    print("night_count_distribution", Counter(night_counts.values()))
    print("split", split_summary)
    print("reproduction", expected_reproduction)
    print("physiology", physiology)
    print("edge_signature_collisions", len(collisions))
    print("outputs", sorted(path.as_posix() for path in OUT.iterdir()))


if __name__ == "__main__":
    main()
