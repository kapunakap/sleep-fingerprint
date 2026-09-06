# Hardware decision

## Verdict: NOT YET

Do **not** buy custom BCG hardware from the evidence in this branch yet.

### Evidence in favor

- The long-term natural-sleep control remains materially above 32-way chance: combined normalized test Rank-1 25.0% versus 3.1% chance in the current chronological-half run.
- Identity signal survives a changed physical BCG measurement path in the PLOS proxy: cross-sensor/location Rank-1 14.2% (participant-bootstrap 95% CI 11.1-17.9%) versus 3.7% chance, Rank-5 40.6% (34.7-46.8%) versus 18.5% chance.
- Shuffled-label cross-sensor controls return to chance and no duplicate edge-signature collisions were detected.

### Evidence against buying now

- Primary nights do not have verified reinstallation boundaries. A persistent participant-specific mattress/sensor/install transfer function remains possible.
- Sensor location is strongly predictable from the same representations: 48-57% accuracy for several feature families versus 12.5% chance.
- In the primary data, early-window enrollment to late-window query collapses to 3.1% Rank-1, exactly cohort chance, exposing strong time/state nonstationarity.
- Simple PLOS BCG-vs-ECG heart-rate validation is weak for these features (about 35 bpm MAE, correlation only ~0.34-0.38).
- A completed frozen-embedding transfer metric on an independent clinical BCG domain is still missing, so Issue #1 success gate 3 is not met.
- The latest hosted GitHub Actions reruns currently fail before any runner steps are assigned, preventing the post-parser-fix primary checkpoint from being regenerated there.

### What would change the verdict

At minimum, obtain one of these without purchasing hardware:

1. a verified repeated-person public dataset with documented removal/reinstallation and explicit identity mapping, or
2. a strong independent frozen-embedding transfer result on `28643153` or `28416896`, followed by a successful post-fix primary run with participant-cluster confidence intervals and reference validation.

Even then, hardware should be purchased only if the setup-changing result stays convincingly above chance after leakage and setup controls.

This is research software, not a diagnostic or medical-device recommendation.
