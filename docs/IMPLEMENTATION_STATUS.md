# Implementation status

This branch is the Phase-1 engineering foundation for issue #1. It intentionally does **not** close the issue.

Implemented now:

- pinned Figshare provenance and resumable download;
- exact size/MD5 verification;
- guarded archive extraction;
- BCG parser and audit manifest;
- deterministic night-disjoint splits;
- 64 Hz preprocessing and two-channel filtering;
- held-out-night handcrafted retrieval baseline;
- 256-D encoder foundation with cross-night-only positives;
- automated software-invariant tests.

Still required before issue #1 can close:

- complete verified public-data execution;
- report real Rank-1/Rank-5 and similarity distributions;
- inspect representative public-data plots;
- train/evaluate the encoder beyond smoke-level foundation;
- frozen-embedding transfer on an independent public BCG dataset;
- final hardware buy / do-not-buy recommendation.
