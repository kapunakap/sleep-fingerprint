# Phase-1 results — fulfilled evidence index

This file began as the Phase-1 results template. The required public-data evidence now exists and is indexed below.

- [x] exact archive size and MD5 verified — `docs/DATASET.md`, `metrics/primary_cross_night/metrics.json`;
- [x] real-data audit counts and QC summary — `metrics/primary_cross_night/night_qc.csv`, `reports/cross-installation.md`;
- [x] representative raw/resampled/filtered plot — `plots/primary_cross_night/signal_example.svg`;
- [x] night-disjoint train/validation/test split — `metrics/primary_cross_night/split_assignments.csv`;
- [x] train-night enrollment vs held-out-night retrieval metrics — `metrics/primary_cross_night/metrics.json`;
- [x] per-participant results and confusion matrix — `metrics/primary_cross_night/per_participant_test.csv`, `metrics/primary_cross_night/test_confusion.csv`;
- [x] encoder smoke test with no same-night positive pairs — `src/sleep_fingerprint/encoder.py`, `tests/test_pipeline.py`;
- [x] test/lint/typecheck closeout validation — `docs/LOCAL_VALIDATION.md`;
- [x] independent-dataset frozen transfer — `metrics/transfer_28643153/`, `reports/transfer.md`;
- [x] setup/confound investigation — `metrics/plos_cross_sensor/`, `reports/cross-installation.md`;
- [x] final hardware decision — `reports/hardware-decision.md`: **NOT YET**.

The completed POC is deliberately not presented as a solved biological fingerprint or clinical validation. The remaining research priority is controlled true reinstallation with explicit installation IDs.
