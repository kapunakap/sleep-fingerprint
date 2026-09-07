import math
import zipfile
from pathlib import Path

import numpy as np
import pytest
import torch

from sleep_fingerprint.dataset import DatasetError, parse_bcg_csv, safe_extract_zip, sanitize_zip_member, verify_archive
from sleep_fingerprint.encoder import CrossNightPairSampler, SleepFingerprintEncoder, WindowRecord
from sleep_fingerprint.preprocess import (
    PreprocessConfig,
    iter_night_windows,
    quality_reasons,
    resample_signal,
    separate_components,
)
from sleep_fingerprint.retrieval import evaluate_retrieval
from sleep_fingerprint.split import make_night_splits


def test_parse_bcg_csv(tmp_path: Path) -> None:
    path = tmp_path / "night_BCG.csv"
    path.write_text("BCG,Timestamp,fs\n1.0,1700000000,140\n2.0,,\n3.0,,\n")
    parsed = parse_bcg_csv(path)
    assert parsed.signal.tolist() == [1.0, 2.0, 3.0]
    assert parsed.source_fs_hz == 140.0
    assert parsed.start_timestamp_utc_plus_08 is not None


def test_parse_resp_reference_header(tmp_path: Path) -> None:
    path = tmp_path / "night_Resp.csv"
    path.write_text("Resp\n1.0\n2.0\n3.0\n")
    parsed = parse_bcg_csv(path, default_fs_hz=20.0)
    assert parsed.signal.tolist() == [1.0, 2.0, 3.0]
    assert parsed.source_fs_hz == 20.0


def test_parse_rejects_bad_value(tmp_path: Path) -> None:
    path = tmp_path / "night_BCG.csv"
    path.write_text("1,1700000000,140\nnope,,\n")
    with pytest.raises(DatasetError, match="malformed"):
        parse_bcg_csv(path)


def test_verify_archive_small_fixture(tmp_path: Path) -> None:
    path = tmp_path / "x"
    path.write_bytes(b"abc")
    result = verify_archive(path, expected_bytes=3, expected_md5="900150983cd24fb0d6963f7d28e17f72")
    assert result["bytes"] == 3


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:\\drive", "a/../../b"])
def test_zip_path_rejected(name: str) -> None:
    with pytest.raises(DatasetError):
        sanitize_zip_member(name)


def test_safe_extract(tmp_path: Path) -> None:
    archive = tmp_path / "safe.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("data/01/BCG/01_20240101_BCG.csv", "1,1700000000,140\n")
    destination = tmp_path / "out"
    result = safe_extract_zip(archive, destination)
    assert result["members"] == 1
    assert (destination / "data/01/BCG/01_20240101_BCG.csv").exists()


def test_resample_length() -> None:
    source = np.linspace(-1, 1, 140 * 61 + 1)
    output = resample_signal(source, 140, 64)
    assert len(output) == math.ceil(len(source) * 64 / 140)


def test_filters_separate_bands() -> None:
    config = PreprocessConfig()
    t = np.arange(config.window_samples) / config.target_fs_hz
    resp_true = np.sin(2 * np.pi * 0.25 * t)
    cardiac_true = 0.35 * np.sin(2 * np.pi * 1.25 * t)
    resp, cardiac = separate_components(resp_true + cardiac_true, config)
    assert np.corrcoef(resp, resp_true)[0, 1] > 0.9
    assert np.corrcoef(cardiac, cardiac_true)[0, 1] > 0.8


def test_flatline_rejected() -> None:
    assert "flatline" in quality_reasons(np.zeros(3840))


def test_window_output_shape() -> None:
    config = PreprocessConfig(window_seconds=4, stride_seconds=2)
    t = np.arange(140 * 12) / 140
    source = np.sin(2 * np.pi * 0.25 * t) + 0.25 * np.sin(2 * np.pi * 1.2 * t)
    accepted = [w for w in iter_night_windows(source, 140, config) if w.accepted]
    assert accepted
    assert accepted[0].signal.shape == (2, config.window_samples)


def test_split_is_deterministic_and_night_disjoint() -> None:
    records = []
    for subject, count in (("A", 5), ("B", 4), ("C", 2)):
        for i in range(count):
            records.append({"subject_id": subject, "night_key": f"{subject}:n{i}", "source_path": f"{subject}/{i}"})
    first = make_night_splits(records, seed=11)
    second = make_night_splits(records, seed=11)
    assert first == second
    assert len(first.by_night()) == len(first.assignments)
    for subject in ("A", "B"):
        assert {x.split for x in first.assignments if x.subject_id == subject} == {"train", "val", "test"}
    assert any(x["subject_id"] == "C" for x in first.exclusions)


def test_retrieval_metrics() -> None:
    result = evaluate_retrieval(
        {"A": np.array([1.0, 0.0]), "B": np.array([0.0, 1.0]), "C": np.array([-1.0, 0.0])},
        [
            {"subject_id": "A", "night_key": "A:test", "embedding": np.array([0.9, 0.1])},
            {"subject_id": "B", "night_key": "B:test", "embedding": np.array([0.1, 0.9])},
            {"subject_id": "C", "night_key": "C:test", "embedding": np.array([-0.9, 0.1])},
        ],
    )
    assert result.metrics["rank_1"] == 1.0
    assert result.metrics["rank_3_capped"] == 1.0
    assert result.metrics["chance_rank_1"] == 1 / 3


def test_encoder_shape_and_norm() -> None:
    model = SleepFingerprintEncoder().eval()
    with torch.no_grad():
        embedding = model(torch.randn(3, 2, 256))
    assert embedding.shape == (3, 256)
    assert torch.allclose(torch.linalg.vector_norm(embedding, dim=1), torch.ones(3), atol=1e-5)


def test_positive_pairs_are_cross_night() -> None:
    sampler = CrossNightPairSampler(
        [
            WindowRecord("a1", "A", "A:n1"),
            WindowRecord("a2", "A", "A:n2"),
            WindowRecord("a3", "A", "A:n3"),
        ],
        seed=7,
    )
    for _ in range(50):
        pair = sampler.sample_pair()
        assert pair.anchor.subject_id == pair.positive.subject_id
        assert pair.anchor.night_key != pair.positive.night_key


def test_same_night_only_is_rejected() -> None:
    with pytest.raises(ValueError):
        CrossNightPairSampler([WindowRecord("a", "A", "A:n1"), WindowRecord("b", "A", "A:n1")])
