# Sleep fingerprint setup-confound evidence

Status: research-only, not diagnostic. This report distinguishes **cross-night**, **cross-sensor/location**, **independent-domain transfer**, and true **cross-installation** evidence.

## Decision

**Hardware verdict: NOT YET.**

Identity is above chance across held-out nights and across changed physical sensor locations, and a frozen source-defined representation now shows measurable independent cardiovascular transfer. But setup is strongly predictable, early-to-late retrieval can collapse to chance, and no verified repeated-person raw BCG dataset with explicit removal/reinstallation mapping has been found.

## Experiment A: primary long-term natural-sleep control

Dataset: Figshare article `26013157`, file `46976602`, `dataset.zip`, 1,624,767,747 bytes, MD5 `5f1b50277e000a56b2b8d3df4f6ad81c`, CC BY 4.0.

Audit: 212 valid BCG nights from 32 participants at 140 Hz. The source does not document sensor removal/reinstallation between nights, so `installation_id` remains unknown and `night_id` is never treated as an installation label.

Chronological protocol: first `floor(n/2)` nights per participant enroll/train; remaining nights are split chronologically into validation and test. Current real measurements from the full run before its late reference-parser failure use 64 validation and 64 test query nights. Chance is 3.125% Rank-1 / 15.625% Rank-5.

| Variant | Test R1 | Test R5 |
|---|---:|---:|
| combined normalized | **25.0%** | **59.4%** |
| cardiac only | 29.7% | 51.6% |
| respiratory only | 12.5% | 43.8% |
| phase-insensitive spectral | 15.6% | 53.1% |
| morphology-heavy | **48.4%** | 67.2% |
| amplitude-bearing | 25.0% | 64.1% |
| deterministic random temporal half | 29.7% | 62.5% |
| early enrollment -> late query | **3.1%** | 23.4% |
| late enrollment -> early query | 10.9% | 23.4% |

The early-to-late collapse is a major confound. The recovered file `metrics/primary_cross_night/recovered_run_33995935636.json` is intentionally marked partial; its fallback query-bootstrap intervals are **not** the requested participant-cluster confidence intervals.

The `Resp` parser bug was fixed in `bf747f1c0a456e83c221ccdad354cb0f89cfbbc3` and regression-tested in `635ae1ecfa7b1146ddfd985275807605e3dcbe23`. Fresh hosted reruns currently fail before runner steps are assigned, so the full post-fix primary package remains pending.

## Experiment B: strongest setup-changing proxy

Ladrova et al., PLOS ONE 2024, DOI `10.1371/journal.pone.0306074`, CC BY: 27 participants, eight simultaneous physical BCG locations S1-S8, 2.5 kHz BCG and ECG.

Interpretation: **cross-sensor / cross-location / cross-placement**, not cross-night and not removal/reinstallation.

Normalized-spectrum cross-sensor result over all 56 directed off-diagonal sensor pairs:

- 1,512 queries
- Rank-1 **14.2%**, participant-bootstrap 95% CI **11.1-17.9%**
- Rank-5 **40.6%**, 95% CI **34.7-46.8%**
- chance 3.7% / 18.5%
- verification AUROC **0.676**
- same-person similarity mean ~0.182
- different-person similarity mean ~-0.010
- duplicate edge-signature collisions: 0
- shuffled-label retrieval returns to chance

Other Rank-1 / Rank-5: cardiac 16.0% / 42.1%; respiratory 5.6% / 24.7%; morphology 13.5% / 41.0%; amplitude-bearing 9.9% / 32.9%.

## Experiment C: setup prediction

Participant-safe prediction of the physical sensor/location is far above 12.5% chance:

- normalized spectrum 48.1%
- cardiac 46.3%
- respiratory 20.8%
- morphology 53.7%
- amplitude-bearing 56.9%

This is strong evidence that the representations retain setup information.

## Experiment D: physiology-reference validation

PLOS BCG-vs-ECG heart-rate checks are weak:

- spectral estimator: n ~216, MAE ~35.6 bpm, correlation ~0.343
- autocorrelation estimator: n ~216, MAE ~35.3 bpm, correlation ~0.377

The primary Polar-H9 / respiratory reference metrics are still pending the complete post-fix run.

## Experiment E: independent frozen transfer

Target: Figshare article `28643153`, **CC BY 4.0**, 46 participants ages 27-93, overnight 125 Hz mattress BCG with synchronized Holter ECG and clinical metadata.

A fixed 28-D source-defined spectral representation is applied unchanged. Only training-fold standardization and a ridge probe are fitted. Splits are subject-only deterministic 5-fold CV.

Results:

- age regression: MAE **11.28 years** vs train-mean baseline **9.69**; RMSE 15.64; Pearson -0.149; Spearman -0.137 — **failed baseline**
- broad AF/flutter: 20 positive / 26 negative, AUROC **0.550**, AUPRC 0.494, balanced accuracy 0.602 — weak
- persistent AF: 17 positive / 29 negative, AUROC **0.712** (subject-bootstrap 95% CI **0.550-0.860**), AUPRC **0.619** (0.461-0.814), balanced accuracy **0.691** (0.551-0.826)

Persistent AF is a measurable frozen independent cardiovascular transfer result, so Issue #1 science gate 3 is supported. It remains exploratory because the endpoint was selected after inspecting the available metadata and after broader age/AF probes were weak.

## What the evidence answers

The strongest exact-sensor-only explanation is falsified: identity survives a changed physical BCG sensor/location above chance. The independent transfer result also shows that a fixed representation contains some cardiovascular-domain information outside the primary cohort.

The evidence does **not** establish a physiology-only identity fingerprint independent of mattress, placement, installation, posture, sleep stage, body position or time of night. Setup predictability, time nonstationarity and the missing true reinstallation dataset remain material confounds.

## Reproduction

```bash
python scripts/run_primary_experiments.py
python scripts/run_plos_cross_sensor.py
python scripts/run_transfer.py
pytest
ruff check src tests scripts
mypy src
```

Raw third-party datasets are not committed or redistributed.