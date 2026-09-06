# sleep-fingerprint

Evidence-first proof of concept for testing whether public raw under-mattress ballistocardiography (BCG) contains a stable participant fingerprint.

**Research software only.** This is not a medical device, diagnostic system, or validated biological-age model.

## Current decision

**Hardware: NOT YET.**

The identity signal is real enough to keep studying, but the current public evidence does **not** establish a physiology-only fingerprint independent of bed/sensor/placement/installation effects.

Key measured evidence:

- primary 32-person natural-sleep control, chronological held-out nights: test Rank-1 **25.0%**, Rank-5 **59.4%** vs 3.1% / 15.6% chance;
- strongest free setup-changing proxy, 27 people across eight physical BCG sensor locations: Rank-1 **14.2%** (participant-bootstrap 95% CI 11.1-17.9%), Rank-5 **40.6%** (34.7-46.8%) vs 3.7% / 18.5% chance, verification AUROC **0.676**;
- sensor-location prediction from the same representations reaches **48-57%** for several feature families vs 12.5% chance;
- primary early-window enrollment -> late-window query falls to **3.1% Rank-1**, exactly cohort chance.

So identity survives a changed physical BCG sensor/location, but setup information is strong and the signal is highly nonstationary. No public dataset with verified repeated-person sensor removal/reinstallation has yet been found.

See:

- `reports/cross-installation.md` — measured evidence and interpretation;
- `reports/dataset-search.md` — public dataset search and exact rejection reasons;
- `reports/hardware-decision.md` — hardware gate;
- `metrics/plos_cross_sensor/` — committed real cross-sensor metrics/CSVs;
- `metrics/primary_cross_night/recovered_run_33995935636.json` — retrieval measurements recovered from the full primary run that failed later during reference parsing.

Issue #1 remains open because a completed frozen-embedding transfer result on an independent BCG domain is still missing.

## Phase-1 source dataset

Primary dataset: Figshare article `26013157`, file `46976602` (`dataset.zip`), dataset provenance pinned as CC BY 4.0.

Pinned public identity:

- size: `1,624,767,747` bytes
- MD5: `5f1b50277e000a56b2b8d3df4f6ad81c`
- BCG source rate: 140 Hz
- cohort: 32 participants, 212 nights
- sensor: H70030 piezoelectric film beneath the mattress around chest position

The paper describes consecutive natural-sleep nights but does **not** establish that the under-mattress sensor was removed/reinstalled between nights. `night_id != installation_id`; unknown setup identifiers remain unknown.

## Strongest setup-changing proxy

Ladrova et al., PLOS ONE 2024, DOI `10.1371/journal.pone.0306074`, CC BY:

- 27 participants;
- eight simultaneous physical BCG locations S1-S8 from head/carotid through leg/femoral;
- 2.5 kHz BCG plus ECG reference;
- enrollment/query use different physical sensors and non-overlapping temporal regions.

This is **cross-sensor / cross-location / cross-placement**, not cross-night or cross-installation.

## Installation-aware metadata

The experiment manifest carries explicit fields for participant, night, session, bed, mattress, sensor, device, installation, sensor position, recording location, dataset, recording date, and provenance. Unknown values stay null. Participant IDs are never reused to synthesize setup IDs.

## Leakage rule

The identity experiment splits by **night**, never by random windows. Enrollment uses train nights; validation/test queries use held-out nights. Positive encoder pairs must be from the same participant on **different nights**. Setup-changing tests use real source sensor IDs and disjoint time regions.

## Implemented experiment surface

- resumable Figshare download with pinned size/MD5 verification;
- guarded extraction and streaming BCG parsing;
- installation-aware provenance manifest;
- deterministic night-disjoint and chronological cross-night splits;
- 140 Hz -> 64 Hz resampling;
- 60-second QC windows;
- respiratory and cardiac channels;
- normalized, cardiac-only, respiratory-only, phase-insensitive spectral, morphology-heavy, amplitude-bearing, temporal-half and early/late ablations;
- same/different-person similarity distributions and verification AUROC;
- participant-cluster bootstrap support;
- shuffled-label and duplicate-signature controls;
- participant-safe setup prediction;
- PLOS cross-sensor/location evidence pipeline;
- physiology-reference validation hooks;
- compact two-channel 256-D L2-normalized PyTorch encoder foundation and cross-night-positive sampler;
- independent-domain probes for public clinical BCG datasets.

## Reproduction

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,encoder]'

# Primary pinned dataset workflow
python -m sleep_fingerprint download --data-dir data
python -m sleep_fingerprint extract --data-dir data --destination data/extracted
python -m sleep_fingerprint audit --dataset-root data/extracted --output-dir data/reports
python scripts/run_primary_experiments.py

# PLOS eight-sensor proxy
python scripts/run_plos_cross_sensor.py

# Independent clinical-domain metadata/sample probe
python scripts/probe_transfer.py
```

Raw third-party datasets and large archives are not committed or redistributed.

## Validation

```bash
pytest
ruff check src tests scripts
mypy src
```

The successful full primary-data GitHub Actions attempt passed 25 tests, ruff, and mypy before the later experiment-stage `Resp` header parser failure. That parser path and a regression test are fixed on the experiment branch. The newest hosted reruns currently fail before runner steps are assigned, so they do not provide a post-fix CI result.

## Success gate

Issue #1 is successful only when all three are true:

- [x] public raw mattress BCG is usable;
- [x] leakage-safe held-out-night identity is materially above chance;
- [ ] a frozen representation/embedding shows measurable transfer to an independent age or cardiovascular task/domain.

Until the third gate is measured and the setup confound is better bounded, the repo stays private and the hardware verdict stays **NOT YET**.
