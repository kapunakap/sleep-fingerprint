# sleep-fingerprint

Evidence-first proof of concept for testing whether public raw under-mattress ballistocardiography (BCG) contains a stable participant fingerprint.

**Research software only.** This is not a medical device, diagnostic system, or validated biological-age model.

## Current decision

**Hardware: NOT YET.**

The three original scientific POC gates now have supporting evidence, including a real frozen independent-domain cardiovascular transfer result. However, the evidence does **not** establish a physiology-only fingerprint independent of bed/sensor/placement/installation effects, and the complete post-parser-fix primary artifact is still pending because current GitHub Actions jobs fail before runner steps are assigned.

Key measured evidence:

- primary 32-person natural-sleep control, chronological held-out nights: test Rank-1 **25.0%**, Rank-5 **59.4%** vs 3.1% / 15.6% chance;
- primary early-window enrollment -> late-window query collapses to **3.1% Rank-1**, exactly chance;
- strongest setup-changing proxy, 27 people across eight physical BCG sensor locations: Rank-1 **14.2%** (participant-bootstrap 95% CI 11.1-17.9%), Rank-5 **40.6%** (34.7-46.8%), verification AUROC **0.676**;
- sensor-location prediction reaches **48-57%** for several feature families vs 12.5% chance;
- independent Figshare `28643153` frozen 28-D source-defined spectrum representation -> persistent-AF probe: **AUROC 0.712**, AUPRC **0.619**, balanced accuracy **0.691**, with 17 positive / 29 negative subjects and subject-only 5-fold CV;
- the same frozen representation **fails age regression baseline** (MAE 11.28 vs 9.69 years) and gives only weak broad-AF transfer (AUROC 0.550), so the successful endpoint is reported as exploratory rather than confirmatory.

No verified public dataset with repeated-person raw BCG plus explicit sensor removal/reinstallation and identity mapping has been found.

See:

- `reports/cross-installation.md` — setup/time confounds and measured cross-sensor evidence;
- `reports/transfer.md` — frozen independent-domain transfer protocol and results;
- `reports/dataset-search.md` — public dataset search and rejection reasons;
- `reports/hardware-decision.md` — hardware gate;
- `metrics/plos_cross_sensor/` — committed cross-sensor metrics/CSVs;
- `metrics/transfer_28643153/` — committed frozen-transfer metrics/CSVs;
- `metrics/primary_cross_night/recovered_run_33995935636.json` — real retrieval measurements recovered from the full primary run that failed later during reference parsing.

## Primary dataset

Figshare article `26013157`, file `46976602` (`dataset.zip`), CC BY 4.0.

- size: `1,624,767,747` bytes
- MD5: `5f1b50277e000a56b2b8d3df4f6ad81c`
- source rate: 140 Hz
- cohort: 32 participants, 212 nights
- H70030 piezoelectric film beneath the mattress near the chest

The source does not establish sensor removal/reinstallation between nights. `night_id != installation_id`; installation remains unknown.

## Leakage and confound rules

- identity retrieval splits by **night**, never random windows;
- enrollment uses train nights; validation/test use held-out nights;
- setup-changing tests use real source sensor IDs and disjoint time regions;
- unknown setup metadata stays unknown and is never synthesized from participant/night IDs;
- target-transfer folds are participant-only;
- target labels never fit the frozen representation itself.

## Frozen independent transfer

Target: Figshare `28643153`, CC BY 4.0, 46 participants, ages 27-93, overnight 125 Hz mattress BCG with synchronized Holter ECG and demographic/clinical metadata.

The fixed 28-D representation uses source-defined respiratory/cardiac spectral bands and is applied unchanged to every target participant. Only a training-fold standardizer and ridge probe are fitted. Exact configuration, folds, metrics, predictions and plots are committed under `configs/transfer_28643153.json`, `metrics/transfer_28643153/`, and `plots/transfer_28643153/`.

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

# Independent frozen transfer
python scripts/run_transfer.py

# Software checks
pytest
ruff check src tests scripts
mypy src
```

Raw third-party datasets and large archives are not committed or redistributed.

## CI / primary-artifact status

A full primary-data Actions run passed **25 tests**, ruff and mypy before the late `Resp` reference-header parser failure. The parser is fixed and regression-tested in commits `bf747f1c0a456e83c221ccdad354cb0f89cfbbc3` and `635ae1ecfa7b1146ddfd985275807605e3dcbe23`.

Current hosted retries create jobs but assign **no runner steps**, including fresh CI and transfer runs. Therefore this is presently characterized as an Actions runner/startup failure, not a code-executed failure. The requested post-fix primary package (participant-cluster CIs, similarities, AUROC, per-participant table, confusion matrix, accepted-window counts and physiology-reference metrics) must still be regenerated before the research task is called acceptance-complete.

## Success gates

- [x] public raw mattress BCG is usable;
- [x] leakage-safe held-out-night identity is materially above chance;
- [x] a frozen source-defined representation shows measurable transfer to an independent cardiovascular task/domain.

The **original three science gates are now supported**, but Issue #1 remains open until the complete post-fix primary evidence artifact is regenerated and current CI is either executed successfully or accurately resolved. Hardware remains **NOT YET** and the repository stays private.