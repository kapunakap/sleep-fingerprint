# Implementation status

Issue #1 public-data POC is acceptance-complete. The repository now contains the engineering foundation, completed primary evidence package, cross-sensor/location confound experiment, independent frozen transfer, and the originally requested representative signal visualization.

Implemented and executed:

- pinned Figshare provenance, resumable download, exact size/MD5 verification, and guarded extraction;
- 32-participant / 212-night primary audit with deterministic chronological night-disjoint splits;
- 140 Hz → 64 Hz preprocessing, QC, respiratory/cardiac band separation, and a committed representative raw/resampled/filtered signal plot;
- held-out-night identity retrieval with participant-cluster confidence intervals, similarities, AUROC, per-participant metrics, confusion matrix, ablations, shuffled-label controls, scalar shortcuts, and duplicate checks;
- primary reference-physiology checks showing strong simple heart-rate agreement but poor respiratory-rate agreement;
- PLOS 27-participant × 8-sensor cross-sensor/location evaluation and setup prediction;
- frozen 28-D independent cardiovascular transfer on Figshare `28643153`;
- 256-D encoder foundation and cross-night-only positive sampler with same-night positives prohibited;
- automated tests, Ruff, mypy, and reproducible research scripts/reports.

The learned encoder foundation is intentionally **not** promoted as the headline scientific result. Transparent handcrafted/frozen features already expose material time/setup confounds, so this POC does not add learned-model complexity merely to chase accuracy before those confounds are resolved.

## Scientific decision

**Hardware: NOT YET.**

The public-data evidence is promising but does not establish a physiology-only fingerprint independent of sensor/bed/placement/installation effects. In particular:

- primary early → late Rank-1 collapses to chance;
- physical sensor/location is strongly predictable;
- primary respiratory validation is poor;
- the simple PLOS heart-rate checks are poor;
- age transfer fails its trivial baseline and broad-AF transfer is weak;
- persistent-AF transfer is exploratory;
- no verified public dataset provides same-person raw BCG across an explicit removal/reinstallation boundary with preserved identity mapping.

The clearest next scientific milestone is a controlled true-reinstallation experiment, not a larger learned encoder.
