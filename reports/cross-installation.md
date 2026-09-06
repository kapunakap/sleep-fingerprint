# Sleep fingerprint setup-confound evidence

Status: research-only, not diagnostic. This report deliberately distinguishes **cross-night**, **cross-sensor/location**, and **cross-installation** evidence.

## Decision

**Hardware verdict: NOT YET.**

The public evidence is promising enough to keep investigating identity signal, but it does not establish a stable physiology-only fingerprint across reinstallation. The strongest free setup-changing proxy remains above chance, while setup itself is highly predictable and a within-night early/late perturbation can collapse identity retrieval to chance. Independent frozen-embedding transfer is also still unresolved.

## Experiment A: primary long-term natural-sleep control

Dataset: Figshare article `26013157`, pinned file `46976602`, `dataset.zip`, 1,624,767,747 bytes, MD5 `5f1b50277e000a56b2b8d3df4f6ad81c`.

Observed audit: 212 valid BCG nights from 32 participants, all at 140 Hz. The source paper describes an H70030 piezoelectric film sensor placed beneath each participant's mattress near the chest and roughly seven consecutive dormitory nights. It does **not** document removal/reinstallation between nights. Therefore `installation_id` remains unknown and `night_id` is never used as an installation label.

Protocol in the current experiment code: sort each participant's nights chronologically; use the first `floor(n/2)` nights for enrollment/training and split the remaining nights chronologically between validation and test. Standardization is fit only on training-night features. Participant enrollment is the normalized average of training-night vectors. Validation/test queries are held-out nights.

A GitHub Actions run at source commit `a00fd4ad2d3a6dddb313ac7560fb7687bc780ed0` completed extraction/features and all retrieval variants on the full 212-night dataset, then failed later while parsing the first respiratory-reference CSV header (`Resp`). The parser bug was subsequently fixed and regression-tested in source, but the latest hosted rerun fails before runner steps are assigned. Consequently the retrieval numbers below are real measurements, but the final post-fix artifact containing participant-cluster confidence intervals, similarities, per-participant tables, confusion matrix, and physiology-reference output has not yet been produced.

### Measured retrieval before the late reference-parser failure

| Variant | Validation R1 | Validation R5 | Test R1 | Test R5 |
|---|---:|---:|---:|---:|
| combined normalized | 29.7% | 65.6% | **25.0%** | **59.4%** |
| cardiac only | 26.6% | 62.5% | 29.7% | 51.6% |
| respiratory only | 14.1% | 40.6% | 12.5% | 43.8% |
| phase-insensitive spectral | 17.2% | 50.0% | 15.6% | 53.1% |
| morphology-heavy | 37.5% | 71.9% | **48.4%** | 67.2% |
| amplitude-bearing | 23.4% | 54.7% | 25.0% | 64.1% |
| deterministic random temporal half | 20.3% | 59.4% | 29.7% | 62.5% |
| early enrollment -> late query | **3.1%** | 23.4% | **3.1%** | 23.4% |
| late enrollment -> early query | 6.3% | 31.3% | 10.9% | 23.4% |

There were 64 validation and 64 test query nights; cohort chance is 3.125% Rank-1 and 15.625% Rank-5.

The combined-normalized test result is materially above chance, but the early-to-late result falls exactly to Rank-1 chance. That strong nonstationarity means the cross-night result cannot safely be interpreted as a stationary participant physiology signature.

`metrics/primary_cross_night/recovered_run_33995935636.json` preserves the exact log-recovered values and clearly marks the run incomplete. It also contains query-level fallback intervals, which are **not** the predeclared participant-cluster bootstrap and therefore are not the final confidence intervals requested by the protocol.

## Experiment B: strongest executable setup-changing proxy

Dataset/paper: Ladrova et al., PLOS ONE 2024, DOI `10.1371/journal.pone.0306074`, Creative Commons Attribution (CC BY). It contains 27 healthy participants, eight simultaneous physical BCG locations (S1-S8) from head/carotid through leg/femoral, 2.5 kHz BCG, and simultaneous ECG.

Interpretation: **cross-sensor / cross-location / cross-placement**, one session per person. It is **not** cross-night and is **not** sensor removal/reinstallation.

Leakage controls:

- source-provided participant and sensor IDs only;
- enrollment/query use different physical sensors;
- enrollment/query use non-overlapping temporal regions;
- all 56 directed off-diagonal sensor pairs are evaluated;
- duplicate edge-signature collisions are checked;
- StandardScaler is fit on enrollment vectors only;
- bootstrap unit is participant.

### Cross-sensor normalized-spectrum result

- participants: 27
- physical sensor locations: 8
- directed cross-sensor pairs: 56
- queries: 1,512
- Rank-1: **14.2%**, participant-bootstrap 95% CI **11.1-17.9%**
- Rank-5: **40.6%**, participant-bootstrap 95% CI **34.7-46.8%**
- chance Rank-1: 3.7%
- chance Rank-5: 18.5%
- verification AUROC: **0.676**
- same-person similarity mean/median: 0.182 / 0.200
- different-person similarity mean/median: -0.010 / -0.016
- shuffled-label Rank-1 mean: 3.66% (95% interval 2.58-4.83%)
- shuffled-label Rank-5 mean: 18.39% (15.54-21.23%)
- duplicate edge-signature collisions: 0

The cross-sensor result remains clearly above chance, so the primary identity effect is not explained solely by one exact physical sensor/location transfer function. However it is weaker than the primary cross-night control (about -10.8 percentage points Rank-1 for combined normalized features), and the protocols are not directly matched.

Other cross-sensor Rank-1 / Rank-5 results:

- cardiac spectrum: 16.0% / 42.1%, AUROC 0.677
- respiratory spectrum: 5.6% / 24.7%, AUROC 0.539
- morphology: 13.5% / 41.0%, AUROC 0.667
- amplitude-bearing: 9.9% / 32.9%, AUROC 0.621

## Experiment C: setup prediction

Sensor-location prediction used participant-safe grouped cross-validation on 216 participant-sensor samples. Chance is 12.5% for eight sensors.

- normalized spectrum: **48.1%**
- cardiac spectrum: **46.3%**
- respiratory spectrum: **20.8%**
- morphology: **53.7%**
- amplitude-bearing: **56.9%**

This is strong evidence that the BCG representations retain physical setup/location information. It is the main reason the above-chance identity results cannot yet be interpreted as physiology-only.

## Negative controls and shortcuts

- shuffled identity labels return to chance in the PLOS proxy;
- cross-sensor enrollment/query regions are temporally disjoint;
- no duplicate edge-signature collisions were found;
- primary retrieval splits by night, never random windows;
- primary setup identifiers remain unknown rather than derived from participant/night IDs;
- early-vs-late and late-vs-early primary tests expose strong time/state dependence;
- amplitude-bearing, normalized, cardiac, respiratory, spectral, and morphology-heavy variants are reported separately rather than selecting only the best result.

## Physiology-reference validation

For the PLOS cross-sensor dataset, the simple BCG heart-rate estimators do detect some ECG-related structure, but agreement is weak:

- spectral estimator: 216 samples, MAE ~35.6 bpm, correlation ~0.343;
- autocorrelation estimator: 216 samples, MAE ~35.3 bpm, correlation ~0.377.

This does not show that the identity representation is predominantly physiological. The primary dataset has Polar H9 RR and respiratory references on subsets of nights; final post-fix primary reference metrics remain pending because the hosted rerun currently fails before runner execution.

## Learned encoder

Not promoted as evidence in this report. A learned encoder would be easy to overfit to the same setup/time shortcuts already demonstrated. The free experiments first need a successful independent frozen-representation transfer result and, ideally, a true repeated-person reinstallation dataset.

## Independent transfer

Candidate `28643153` contains 46 middle-aged/elderly participants, overnight 125 Hz BCG, synchronized Holter ECG, and demographic/clinical labels including AF. The branch probe successfully verified the metadata workbook and a BCG sample. Candidate `28416896` contains 85 participants and 152 synchronized BCG/ECG/echocardiography recording folders with clinical/demographic metadata.

No completed frozen-embedding transfer metric is available yet. Therefore Issue #1 success gate 3 is **not met** and the issue must remain open.

## What this experiment answers

The current evidence falsifies the strongest version of the hypothesis that identity recognition is *only* an exact-sensor/location signature: recognition survives a change to another physical BCG sensor/location at 14.2% Rank-1 versus 3.7% chance.

It does **not** establish a participant physiology fingerprint independent of mattress, installation, posture, sleep stage, body position, time-of-night, or transfer function. Setup is strongly predictable, time-of-night perturbation can destroy retrieval, and no true public reinstallation test has been verified.

## Reproduction

Primary full run:

```bash
python scripts/run_primary_experiments.py
```

PLOS cross-sensor run:

```bash
python scripts/run_plos_cross_sensor.py
```

Software checks:

```bash
pytest
ruff check src tests scripts
mypy src
```

Raw third-party datasets are not committed or redistributed.
