# Sleep Fingerprint

**Can a sensor under your mattress recognize who is sleeping?**

This project tests a simple idea: your heartbeat, breathing, and tiny body movements shake the mattress in a pattern that may be partly unique to you.

<p align="center">
  <img src="docs/readme-overview.svg" alt="Sleep Fingerprint explained in plain English: a sensor under the mattress records body vibrations, a computer tries to recognize the sleeper on different nights, it performs much better than random on the normal test, but falls back to random on a harder time-separated test, so hardware is not ready yet." width="100%">
</p>

> **TL;DR:** The sensor can recognize people **better than random**, so there is a real identity signal. But on a harder test the result falls back to random, which means time or sensor setup may be helping. **Promising research; not ready for hardware yet.**

**Research software only.** This is not a medical device, diagnostic system, or validated biological-age model.

## Technical results

The public-data POC is reproducible end-to-end, including the post-parser-fix 212-night primary package and an independent frozen cardiovascular-transfer experiment. The evidence is promising but does **not** establish a physiology-only fingerprint independent of bed/sensor/placement/installation effects.

Key measured evidence:

- primary 32-person natural-sleep control, chronological held-out nights: participant-weighted test Rank-1 **25.0%** (participant-bootstrap 95% CI **14.1-37.5%**) and Rank-5 **59.4%** (**43.8-75.0%**) vs 3.1% / 15.6% chance; raw test query count is 54;
- primary verification AUROC **0.817**; same-person cosine similarity mean **0.472** vs different-person **-0.014**;
- primary early-window enrollment -> late-window query collapses to **3.1% Rank-1**, exactly chance;
- primary BCG-vs-reference heart rate is strong in this simple spectral check: 42 matched nights, MAE **2.42 bpm**, median AE **2.00 bpm**, Pearson **0.960**; respiratory-rate validation is poor: 53 matched nights, MAE **8.49 bpm**, median AE **7.50 bpm**, Pearson **-0.149**;
- strongest setup-changing proxy, 27 people across eight physical BCG sensor locations: Rank-1 **14.2%** (participant-bootstrap 95% CI 11.1-17.9%), Rank-5 **40.6%** (34.7-46.8%), verification AUROC **0.676**;
- sensor-location prediction reaches **48-57%** for several feature families vs 12.5% chance, showing strong setup information;
- independent Figshare `28643153` frozen 28-D source-defined spectrum representation -> persistent-AF probe: **AUROC 0.712**, AUPRC **0.619**, balanced accuracy **0.691**, with 17 positive / 29 negative subjects and subject-only 5-fold CV;
- the same frozen representation **fails age regression baseline** (MAE 11.28 vs 9.69 years) and gives only weak broad-AF transfer (AUROC 0.550), so the successful endpoint is reported as exploratory rather than confirmatory.

No verified public dataset currently combines repeated identity-mapped participants, an explicit removal/reinstallation boundary, raw BCG, and participant mapping across installations.

## What the sensor actually sees

The example below is a representative QC-accepted primary-dataset segment showing the raw/resampled BCG signal and derived respiratory/cardiac structure.

<p align="center">
  <img src="plots/primary_cross_night/signal_example.svg" alt="Representative under-mattress BCG signal with derived respiratory and cardiac structure" width="100%">
</p>

## Research artifacts

- `reports/cross-installation.md` — primary cross-night and setup-confound evidence;
- `reports/transfer.md` — frozen independent-domain transfer protocol and results;
- `reports/dataset-search.md` — public dataset search and rejection reasons;
- `reports/hardware-decision.md` — hardware gate;
- `metrics/primary_cross_night/` and `plots/primary_cross_night/` — completed post-fix primary package;
- `metrics/plos_cross_sensor/` and `plots/plos_cross_sensor/` — fresh cross-sensor/location rerun;
- `metrics/transfer_28643153/` — completed frozen-transfer metrics;
- `metrics/primary_cross_night/recovered_run_33995935636.json` — preserved partial historical recovery artifact, not used as the final primary package.

## Primary dataset and protocol

Figshare article `26013157`, file `46976602` (`dataset.zip`), **CC BY 4.0**.

- exact size: `1,624,767,747` bytes
- MD5: `5f1b50277e000a56b2b8d3df4f6ad81c`
- source rate: 140 Hz
- cohort: 32 participants, 212 valid nights
- H70030 piezoelectric film beneath the mattress near the chest

Per participant, the first `floor(n/2)` chronological nights are enrollment/train. Remaining nights are split chronologically with `ceil(heldout/2)` for validation and the rest for test: **94 train / 64 validation / 54 test nights**. Rank estimates are participant-weighted means; `query_count` remains the raw held-out-night count.

The source does not establish sensor removal/reinstallation between nights. `night_id != installation_id`; installation remains unknown. Therefore this is **cross-night**, not cross-installation.

The extractor accepted all 212 nights and **181,557** windows. Rejected-window counts are **not retained by the current extractor; do not infer**. The representative signal SVG is a derived visualization from the CC BY 4.0 primary source; the repository still does not redistribute the raw archive or raw CSVs.

## Leakage and confound rules

- identity retrieval splits by **night**, never random windows;
- enrollment uses train nights; validation/test use held-out nights;
- setup-changing tests use real source sensor IDs and disjoint time regions;
- unknown setup metadata stays unknown and is never synthesized from participant/night IDs;
- target-transfer folds are participant-only;
- target labels never fit the frozen representation itself.

## Frozen independent transfer

Target: Figshare `28643153`, **A ballistocardiogram dataset with reference ECG signals for bedside heart rhythm assessment**, CC BY 4.0, 46 participants, ages 27-93, overnight 125 Hz mattress BCG with synchronized Holter ECG and demographic/clinical metadata.

The fixed 28-D representation uses source-defined respiratory/cardiac spectral bands and is applied unchanged to every target participant. Only a training-fold standardizer and ridge probe are fitted. Exact configuration, folds, metrics, predictions and plots are committed under `configs/transfer_28643153.json`, `metrics/transfer_28643153/`, and `plots/transfer_28643153/`.

## Reproduction

`requirements/research-lock.txt` records the resolved Python 3.11 research/QA environment. Use it as a constraints file so the scientific stack is repeatable while the package metadata can retain normal lower-bound compatibility.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip

# Linux CI uses the CPU wheel explicitly to avoid pulling CUDA packages.
python -m pip install "torch==2.14.0" --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e '.[dev,encoder]' -c requirements/research-lock.txt
python -m pip check

python scripts/run_primary_experiments.py
python scripts/run_plos_cross_sensor.py
python scripts/run_transfer.py

pytest
ruff check src tests scripts
mypy src
git diff --check
```

On macOS, install `.[dev,encoder]` with the same constraints file and let PyPI provide the native PyTorch wheel; the explicit CPU index above is only for Linux CI/research runners.

The primary runner pins and verifies the Figshare archive, extracts it safely, audits 212 nights, runs the leakage-safe experiment and negative controls, validates reference physiology, checks the exact historical reproduction checkpoint, then writes the final package. Raw third-party datasets and large archives are not committed or redistributed.

## CI status

Hosted GitHub Actions on `main` is green: the project environment installs successfully and the pytest, Ruff, and mypy gates execute successfully. Heavy public-data research workflows are separate manual jobs and publish generated results as workflow artifacts instead of writing back to repository branches.

## POC conclusion

The three Issue #1 science gates are supported by public data, but setup/time confounds remain material. Cross-night identity is clearly above chance and survives a changed physical BCG location above chance; a frozen independent cardiovascular probe is measurable. However, setup is strongly predictable, early-to-late identity collapses to chance, respiration validation is poor, and a true same-person reinstallation dataset is still missing.

**Hardware verdict: NOT YET.**
