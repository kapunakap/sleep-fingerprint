# Release status

The Issue #1 foundation and research stack has been reconciled and merged without force-pushing or rewriting the experiment history.

Merged release layers:

- PR #2 — Phase-1 engineering foundation;
- PR #3 — completed primary/PLOS/transfer evidence and reports;
- PR #4 — representative primary raw/resampled/filtered signal visualization discovered as missing during the final deliverable audit.

The final merged tree contains all original Issue #1 deliverables. The hardware decision remains **NOT YET** because the POC still lacks true same-person reinstallation evidence and retains material setup/time confounds.

Hosted CI remains characterized separately from local validation: observed GitHub Actions jobs fail before workflow-step execution (`steps: null`), while the exact merge-candidate and final merged trees pass pytest, Ruff, mypy, and `git diff --check` locally.
