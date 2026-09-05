from __future__ import annotations

import numpy as np
import pytest

from sleep_fingerprint.experiment import (
    assert_disjoint_intervals,
    bootstrap_group_mean_ci,
    require_real_label_provenance,
    shuffled_label_control,
)
from sleep_fingerprint.manifest import (
    assert_evaluation_label_is_source_backed,
    assert_installation_ids_are_source_backed,
    primary_manifest_record,
)
from sleep_fingerprint.plos_multichannel import FEATURE_VARIANTS, temporal_blocks, window_features


def test_bootstrap_group_mean_is_participant_weighted_and_deterministic() -> None:
    groups = {"A": [1.0, 1.0], "B": [0.0], "C": [0.0, 0.0, 0.0]}
    first = bootstrap_group_mean_ci(groups, repetitions=500, seed=7)
    second = bootstrap_group_mean_ci(groups, repetitions=500, seed=7)
    assert first == second
    assert first["estimate"] == pytest.approx(1 / 3)
    assert first["bootstrap_unit_count"] == 3


def test_shuffled_label_control_is_near_chance() -> None:
    matrix = np.eye(8)
    result = shuffled_label_control([matrix], repetitions=2000, seed=11)
    assert result["rank_1_mean"] == pytest.approx(1 / 8, abs=0.02)
    assert result["rank_5_mean"] == pytest.approx(5 / 8, abs=0.03)


def test_temporal_blocks_are_strictly_disjoint() -> None:
    ranges = temporal_blocks(int(12 * 60 * 2500))
    intervals = [(name, start, end) for name, (start, end) in ranges.items()]
    assert_disjoint_intervals(intervals)
    assert ranges["enroll"][1] <= ranges["middle"][0]
    assert ranges["middle"][1] <= ranges["query"][0]


def test_feature_variants_are_finite() -> None:
    fs = 125.0
    t = np.arange(int(30 * fs)) / fs
    signal = 0.3 * np.sin(2 * np.pi * 0.25 * t) + np.sin(2 * np.pi * 1.2 * t) + 0.05 * np.sin(2 * np.pi * 7 * t)
    dimensions: dict[str, int] = {}
    for variant in FEATURE_VARIANTS:
        vector = window_features(signal, fs, variant)
        assert np.all(np.isfinite(vector))
        assert vector.ndim == 1
        dimensions[variant] = vector.size
    assert len(set(dimensions.values())) >= 3


def test_primary_manifest_refuses_to_invent_installation() -> None:
    record = primary_manifest_record(
        participant_id="01",
        night_id="20240101",
        source_path="01/BCG/01_20240101_BCG.csv",
        recording_date="20240101",
    )
    assert record.installation_id is None
    assert record.bed_id is None
    assert record.mattress_id is None
    assert "not treated as installation" in (record.installation_id_provenance or "")
    assert_installation_ids_are_source_backed([record])
    assert_evaluation_label_is_source_backed([record], label_field="participant_id")
    with pytest.raises(ValueError, match="unknown"):
        assert_evaluation_label_is_source_backed([record], label_field="installation_id")


def test_generic_label_provenance_rejects_synthetic_shortcuts() -> None:
    require_real_label_provenance(
        [{"sensor": "S4", "sensor_provenance": "paper-defined physical channel label"}],
        label_field="sensor",
        provenance_field="sensor_provenance",
    )
    with pytest.raises(ValueError, match="unsafe provenance"):
        require_real_label_provenance(
            [{"sensor": "P01", "sensor_provenance": "inferred from participant"}],
            label_field="sensor",
            provenance_field="sensor_provenance",
        )
