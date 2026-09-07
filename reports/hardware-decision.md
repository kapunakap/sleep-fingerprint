# Hardware decision

## Verdict: NOT YET

Do **not** buy custom BCG hardware from the evidence in this branch yet.

### Evidence in favor

- The complete post-parser-fix primary package now exists and passes its exact historical reproduction checkpoint: 32 participants, 212 nights, 94/64/54 chronological train/validation/test nights.
- Primary participant-weighted test Rank-1 is **25.0%** (participant-bootstrap 95% CI **14.1-37.5%**) versus 3.1% chance; Rank-5 is **59.4%** (**43.8-75.0%**) versus 15.6% chance; verification AUROC is **0.817**.
- Primary BCG-vs-Polar-H9/RR heart-rate validation is strong in this simple spectral check: 42 matched nights, MAE **2.42 bpm**, median AE **2.00 bpm**, Pearson **0.960**.
- Identity survives a changed physical BCG sensor/location in the PLOS proxy: Rank-1 **14.2%** (participant-bootstrap 95% CI 11.1-17.9%) versus 3.7% chance; Rank-5 **40.6%** (34.7-46.8%) versus 18.5% chance.
- Shuffled labels return to chance and duplicate edge-signature collisions are zero.
- A real independent frozen-representation transfer exists on Figshare `28643153`: persistent-AF AUROC **0.712**, AUPRC **0.619**, balanced accuracy **0.691** over 46 subject-only CV predictions (17 positive / 29 negative). AUROC subject-bootstrap 95% CI is **0.550-0.860**.

### Evidence against buying now

- Primary nights still lack verified removal/reinstallation boundaries. A persistent participant-specific mattress/sensor/install transfer function remains possible.
- Sensor location is strongly predictable from the same representations: about **48-57%** for several feature families versus 12.5% chance.
- Primary early-window enrollment -> late-window query collapses to **3.1% Rank-1**, exactly chance, showing severe time/state nonstationarity.
- Primary respiratory-rate validation is poor: 53 matched nights, MAE **8.49 bpm**, median AE **7.50 bpm**, Pearson **-0.149**.
- Fresh PLOS BCG-vs-ECG simple heart-rate estimators are also weak: spectral MAE **49.29 bpm**, Pearson **-0.093**; autocorrelation MAE **37.02 bpm**, Pearson **-0.042** over 216 sensor-level windows.
- Independent transfer is mixed: age regression fails its train-mean baseline (MAE 11.28 vs 9.69 years) and broad-AF AUROC is only 0.550. Persistent AF is a stronger but exploratory endpoint selected after inspecting available clinical metadata, not a preregistered confirmatory result.
- No verified public repeated-person raw BCG dataset combines explicit sensor removal/reinstallation with preserved identity mapping across installations.

### What would change the verdict

A controlled true reinstallation experiment is now the clearest missing evidence. The same participants should be measured across explicit sensor removal/reinstallation (preferably mattress/position perturbations too), with the protocol fixing enrollment/query time regions and preserving raw BCG plus participant/install IDs. The current evidence is strong enough to justify continued software/data research, but not enough to justify custom hardware as the next move.

The three Issue #1 public-data science gates are supported. That does not override the unresolved setup/time confounds.

This is research software, not a diagnostic or medical-device recommendation.
