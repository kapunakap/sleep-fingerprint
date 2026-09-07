# Sleep fingerprint setup-confound evidence

Status: research-only, not diagnostic. This report distinguishes **cross-night**, **cross-sensor/location**, **independent-domain transfer**, and true **cross-installation** evidence.

## Decision

**Hardware verdict: NOT YET.**

The completed post-parser-fix primary experiment shows participant identity above chance across held-out nights, and the PLOS proxy shows identity above chance across changed physical BCG sensor locations. A frozen source-defined representation also shows measurable independent cardiovascular transfer. But setup is strongly predictable, early-to-late retrieval collapses to chance, respiratory-rate validation is poor, and no verified repeated-person raw BCG dataset with an explicit removal/reinstallation boundary and identity mapping has been found.

## Experiment A: primary long-term natural-sleep control

Dataset: Figshare article `26013157`, file `46976602`, `dataset.zip`, 1,624,767,747 bytes, MD5 `5f1b50277e000a56b2b8d3df4f6ad81c`, CC BY 4.0.

Audit: 212 valid BCG nights from 32 participants at 140 Hz. The source does not document sensor removal/reinstallation between nights, so `installation_id` remains unknown and `night_id` is never treated as an installation label. This is **cross-night**, not cross-installation.

Chronological protocol: first `floor(n/2)` nights per participant enroll/train; remaining nights split chronologically with `ceil(heldout/2)` to validation and the rest to test. Final split: **94 train / 64 validation / 54 test nights**. Rank estimates are participant-weighted means; query count is the raw held-out-night count.

Combined-normalized retrieval:

- validation: Rank-1 **29.7%** (participant-bootstrap 95% CI **17.2-42.2%**), Rank-5 **65.6%** (**51.6-79.7%**), 64 raw queries;
- test: Rank-1 **25.0%** (**14.1-37.5%**), Rank-5 **59.4%** (**43.8-75.0%**), 54 raw queries;
- chance: **3.125% Rank-1 / 15.625% Rank-5**;
- test verification AUROC: **0.817**;
- test same-person similarity: mean **0.472**, median **0.573**, 5th-95th percentile **-0.239 to 0.905**;
- test different-person similarity: mean **-0.014**, median **-0.019**, 5th-95th percentile **-0.640 to 0.641**.

Ablations on test:

| Variant | Rank-1 | Rank-5 |
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

The early-to-late Rank-1 result is exactly chance and is a major nonstationarity confound.

The completed extractor accepted **212 nights** and **181,557 windows**. It does not retain rejected-window counts; **do not infer them**. Test confusion contains 54 raw queries and 15 diagonal top-1 hits; this raw diagonal fraction differs from the reported 25.0% participant-weighted Rank-1 because subjects contribute unequal numbers of test nights.

Negative controls:

- shuffled-label test Rank-1 mean **3.10%**, Rank-5 mean **15.61%** over 500 repetitions, consistent with chance;
- duration-only scalar shortcut: test Rank-1 **7.41%**, Rank-5 **31.48%**, above chance but far below the stronger representations;
- start-hour shortcut has zero eligible queries because source start-hour metadata is unavailable rather than synthesized;
- 424 primary edge signatures, **0 duplicate/resampled-edge collisions**.

## Experiment B: strongest setup-changing proxy

Ladrova et al., PLOS ONE 2024, DOI `10.1371/journal.pone.0306074`, CC BY 4.0: 27 participants, eight simultaneous physical BCG locations S1-S8, 2.5 kHz BCG and ECG.

Interpretation: **same-session cross-sensor / cross-location / cross-placement**, not cross-night and not removal/reinstallation. Enrollment uses the first contiguous third after a 30 s margin and query uses the last third. All 56 directed off-diagonal sensor pairs are evaluated.

Fresh rerun normalized-spectrum result:

- 1,512 queries
- Rank-1 **14.2%**, participant-bootstrap 95% CI **11.1-17.9%**
- Rank-5 **40.6%**, 95% CI **34.7-46.8%**
- chance **3.7% / 18.5%**
- verification AUROC **0.676**
- same-person similarity mean **0.182**
- different-person similarity mean **-0.010**
- duplicate edge-signature collisions: **0**

Other Rank-1 / Rank-5: cardiac 16.0% / 42.1%; respiratory 5.6% / 24.7%; morphology 13.5% / 41.0%; amplitude-bearing 9.9% / 32.9%.

## Experiment C: setup prediction

Participant-safe prediction of physical sensor/location is far above 12.5% chance for several feature families:

- normalized spectrum **48.1%**
- cardiac spectrum **46.3%**
- respiratory spectrum **20.8%**
- morphology **53.7%**
- amplitude-bearing **56.9%**

This is strong evidence that the representations retain setup information.

## Experiment D: physiology-reference validation

Primary matched reference nights:

- Polar-H9/RR heart reference: **42 nights**, **1,260,338 reference samples**; BCG spectral estimator MAE **2.42 bpm**, median AE **2.00 bpm**, Pearson **0.960**;
- respiratory reference: **53 nights**, **30,821,528 reference samples**; BCG spectral estimator MAE **8.49 bpm**, median AE **7.50 bpm**, Pearson **-0.149**.

The simple primary heart-rate check is strong; the respiratory check is poor.

The fresh PLOS rerun resolves the previously stale physiology prose and reproduces the committed artifact:

- spectral estimator: **216 windows**, MAE **49.29 bpm**, median AE **40.08 bpm**, Pearson **-0.093**;
- autocorrelation estimator: **216 windows**, MAE **37.02 bpm**, median AE **31.77 bpm**, Pearson **-0.042**.

These simple PLOS estimators are weak and should not be described as ~35 bpm MAE with positive ~0.35 correlation.

## Experiment E: independent frozen transfer

Target: Figshare article `28643153`, **CC BY 4.0**, 46 participants ages 27-93, overnight 125 Hz mattress BCG with synchronized Holter ECG and clinical metadata.

A fixed 28-D source-defined spectral representation is applied unchanged. Only training-fold standardization and a ridge probe are fitted. Splits are deterministic subject-only 5-fold CV, seed `20260906`.

Results:

- age regression: MAE **11.28 years** vs train-mean baseline **9.69**; RMSE 15.64; Pearson -0.149; Spearman -0.137 — **failed baseline**;
- broad AF/flutter: 20 positive / 26 negative, AUROC **0.550**, AUPRC 0.494, balanced accuracy 0.602 — weak;
- persistent AF: 17 positive / 29 negative, AUROC **0.712** (subject-bootstrap 95% CI **0.550-0.860**), AUPRC **0.619** (**0.461-0.814**), balanced accuracy **0.691** (**0.551-0.826**).

Persistent AF is an **exploratory, measurable transfer** result, not confirmatory clinical validation. The endpoint was selected after inspecting available metadata and after broader age/AF probes were weak.

## What the evidence answers

The strongest exact-sensor-only explanation is falsified: identity survives a changed physical BCG sensor/location above chance. The independent transfer result also shows that a fixed representation contains some cardiovascular-domain information outside the primary cohort.

The evidence does **not** establish a physiology-only identity fingerprint independent of mattress, placement, installation, posture, sleep stage, body position, or time of night. Setup predictability, time nonstationarity, poor respiration validation, and the missing true reinstallation dataset remain material confounds.

## Reproduction

```bash
python scripts/run_primary_experiments.py
python scripts/run_plos_cross_sensor.py
python scripts/run_transfer.py
pytest
ruff check src tests scripts
mypy src
git diff --check
```

Raw third-party datasets are not committed or redistributed.
