# sleep-fingerprint

Evidence-first proof of concept for learning a stable **cross-night sleep fingerprint** from public raw under-mattress ballistocardiography (BCG).

This repository is research software only. It is not a medical device, diagnostic system, or validated biological-age model.

## Phase-1 source dataset

Primary dataset: Figshare article `26013157`, file `46976602` (`dataset.zip`), CC BY 4.0.

Pinned public identity:

- size: `1,624,767,747` bytes
- MD5: `5f1b50277e000a56b2b8d3df4f6ad81c`
- BCG source rate: nominally ~140 Hz
- cohort: 32 participants, multiple nights

## Leakage rule

The identity experiment splits by **night**, never by random windows. Enrollment uses train nights. Validation/test queries use held-out nights. Positive encoder pairs must be from the same participant on **different nights**.

## Implemented foundation

- resumable Figshare download with pinned size/MD5 verification;
- zip-slip/symlink-safe extraction;
- BCG discovery and streaming CSV parser;
- per-night manifest and aggregate audit;
- deterministic night-disjoint train/validation/test splits;
- 140 Hz -> 64 Hz polyphase resampling;
- 60-second windows with QC;
- respiratory (0.08–0.7 Hz) and cardiac (0.7–15 Hz) channels;
- leakage-safe handcrafted night-level retrieval baseline;
- compact two-channel 256-D L2-normalized PyTorch encoder;
- cross-night-only positive sampler;
- tests for parser, extraction, preprocessing, split leakage, retrieval, and encoder invariants.

## Quick start

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,encoder]'

python -m sleep_fingerprint download --data-dir data
python -m sleep_fingerprint extract --data-dir data --destination data/extracted
python -m sleep_fingerprint audit --dataset-root data/extracted --output-dir data/reports
python -m sleep_fingerprint baseline \
  --manifest data/reports/manifest.csv \
  --splits data/reports/night_splits.json \
  --dataset-root data/extracted \
  --output-dir data/reports/baseline \
  --max-windows-per-night 12
```

## Validation

```bash
pytest
ruff check src tests
mypy src
```

Synthetic tests are only software checks. They are **not** scientific results. Issue #1 remains open until the real public-data run demonstrates materially-above-chance held-out-night identification and a frozen-embedding transfer result on an independent dataset.

The source cohort is narrowly aged (reported 19–27 years), so it cannot support a strong age conclusion. Chronological-age prediction is not automatically biological-age validation.
