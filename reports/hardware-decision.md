# Hardware decision

## Verdict: NOT YET

Do **not** buy custom BCG hardware from the evidence in this branch yet.

### Evidence in favor

- Primary natural-sleep identity remains materially above 32-way chance: combined normalized test Rank-1 25.0% versus 3.1% chance, Rank-5 59.4% versus 15.6%.
- Identity survives a changed physical BCG sensor/location in the PLOS proxy: Rank-1 14.2% (participant-bootstrap 95% CI 11.1-17.9%) versus 3.7% chance; Rank-5 40.6% (34.7-46.8%) versus 18.5% chance.
- Shuffled labels return to chance and duplicate edge-signature collisions are zero.
- A real independent frozen-representation transfer now exists on Figshare `28643153`: persistent-AF AUROC 0.712, AUPRC 0.619, balanced accuracy 0.691 over 46 subject-only CV predictions (17 positive / 29 negative). The AUROC subject-bootstrap 95% CI is 0.550-0.860.

### Evidence against buying now

- Primary nights still lack verified removal/reinstallation boundaries. A persistent participant-specific mattress/sensor/install transfer function remains possible.
- Sensor location is strongly predictable from the same representations: about 48-57% for several feature families versus 12.5% chance.
- Primary early-window enrollment -> late-window query collapses to 3.1% Rank-1, exactly chance, showing severe time/state nonstationarity.
- Simple PLOS BCG-vs-ECG heart-rate validation is weak (about 35 bpm MAE; correlation ~0.34-0.38).
- Independent transfer is mixed: age regression fails its train-mean baseline (MAE 11.28 vs 9.69 years) and broad-AF AUROC is only 0.550. Persistent AF is a stronger but exploratory endpoint selected after inspecting the available clinical metadata, not a preregistered confirmatory result.
- The complete post-parser-fix primary artifact has not been regenerated. Current GitHub Actions jobs fail before runner steps are assigned, so participant-cluster CIs, primary similarity distributions/AUROC, per-participant table, confusion matrix, accepted-window counts and primary reference-physiology metrics remain pending.
- No verified public repeated-person raw BCG dataset with explicit sensor removal/reinstallation and identity mapping has been found.

### What would change the verdict

Before spending on custom hardware, finish the post-fix primary evidence package and preferably obtain a true reinstallation test or another strong setup-changing dataset. If the independent transfer and identity signal remain above chance after those controls, proprietary data collection may become justified.

The original three Issue #1 science gates are now supported, but that is not enough to override the unresolved setup/time confounds and missing final primary package.

This is research software, not a diagnostic or medical-device recommendation.