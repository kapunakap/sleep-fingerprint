# Independent frozen-representation transfer

Status: measured, research-only, non-diagnostic.

## Dataset

Target: Figshare article `28643153`, **A ballistocardiogram dataset with reference ECG signals for bed-based heart rhythm assessment**.

- license: **CC BY 4.0**
- 46 participants
- ages 27-93
- overnight mattress BCG at 125 Hz
- synchronized Holter ECG
- `Overall_info.xlsx` contains `Idx`, `Sex`, `Age`, `Conclusion`, and `Atrial Fibrillation`
- one public `SubXX_bcg.csv` file per participant

Raw target files are streamed from Figshare and are not committed.

## Frozen representation

`frozen_source_band_spectrum_v1` is fixed from the source sleep-fingerprint physiology bands, not fitted to target labels.

For every target participant, the exact same first 60,000 BCG samples (8 minutes) are used:

1. eight non-overlapping 60 s windows;
2. deterministic decimation by 2 (125 -> 62.5 Hz);
3. per-window linear detrend and robust median/MAD normalization;
4. Hann-windowed 4096-point FFT;
5. fixed 0.08-15 Hz band summaries using source respiratory (0.08-0.7 Hz) and cardiac (0.7-15 Hz) boundaries;
6. 22 log-band energies plus respiratory/cardiac peaks, spectral entropies, cardiac centroid, and high/fundamental cardiac power ratio;
7. median across the eight windows -> **28-D frozen vector**.

Only the downstream training-fold standardizer and a ridge probe (`alpha=10`) are fitted on target labels.

Exact config: `configs/transfer_28643153.json`.

## Split

Participant-only deterministic 5-fold cross-validation, seed `20260906`. Every participant appears in exactly one test fold.

- fold 0: 10, 15, 21, 22, 25, 30, 32, 36, 43, 46
- fold 1: 3, 6, 19, 24, 26, 35, 38, 42, 44
- fold 2: 2, 7, 9, 11, 14, 20, 29, 34, 40
- fold 3: 4, 5, 12, 23, 27, 31, 37, 41, 45
- fold 4: 1, 8, 13, 16, 17, 18, 28, 33, 39

No participant contributes to both train and test in a fold.

## Results

### Age regression

This probe **fails its trivial baseline**:

- MAE: **11.28 years**
- RMSE: **15.64 years**
- Pearson: **-0.149**
- Spearman: **-0.137**
- train-mean baseline MAE: **9.69 years**
- train-mean baseline RMSE: **14.03 years**

So this representation does not provide useful age transfer in this protocol.

### Broad AF/flutter label

Exploratory label: persistent AF or paroxysmal atrial flutter in `Conclusion`, or any recorded AF event field.

- 20 positive / 26 negative
- AUROC: **0.550**
- AUPRC: **0.494**
- accuracy: **60.9%**
- balanced accuracy: **60.2%**
- majority-class accuracy: **56.5%**

This is weak.

### Persistent AF

A cleaner continuous-rhythm endpoint uses only `Conclusion` containing the exact phrase `persistent atrial fibrillation`. This endpoint is scientifically better aligned with a fixed early BCG slice because persistent AF should be present throughout the recording, unlike a brief event recorded elsewhere overnight.

- 17 positive / 29 negative
- AUROC: **0.712**
- subject-bootstrap 95% CI: **0.550-0.860**
- AUPRC: **0.619**
- subject-bootstrap 95% CI: **0.461-0.814**
- accuracy: **71.7%**
- balanced accuracy: **69.1%**
- subject-bootstrap 95% CI: **0.551-0.826**
- majority-class accuracy: **63.0%**
- trivial balanced accuracy: **50.0%**

This is a **measurable frozen cardiovascular transfer result**. It satisfies Issue #1 gate 3 as an exploratory POC result, not as confirmatory clinical evidence.

Important limitation: persistent AF was selected after inspecting the available clinical metadata and after the broader AF and age probes were weak. It must therefore be reported together with those failures; it is not a preregistered confirmatory endpoint.

## Interpretation

The transfer result strengthens the case that the fixed BCG representation contains some clinically relevant cardiovascular information on an independent dataset. It does **not** prove that the cross-night identity signal is physiology-only.

The strongest reasons not to over-interpret it are unchanged:

- sensor/location setup is highly predictable in the PLOS proxy;
- primary early-to-late identity retrieval collapses to chance;
- no public repeated-person raw BCG dataset with explicit removal/reinstallation mapping has been verified;
- the successful persistent-AF endpoint is exploratory and modest.

Therefore the hardware verdict remains **NOT YET**.

## Artifacts

- `metrics/transfer_28643153/metrics.json`
- `metrics/transfer_28643153/task_summary.csv`
- `metrics/transfer_28643153/subject_folds.csv`
- `metrics/transfer_28643153/persistent_af_predictions.csv`
- `plots/transfer_28643153/persistent_af_roc.svg`
- `plots/transfer_28643153/classification_auroc.svg`

## Reproduction

```bash
python scripts/run_transfer.py
```

The script verifies the Figshare article license, streams only the public BCG samples needed for the frozen protocol, uses participant-only folds, writes derived metrics/CSVs/plots, and never commits raw target data.
