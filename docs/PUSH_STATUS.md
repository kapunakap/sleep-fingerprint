# Release status

The Issue #1 foundation and research stack has been reconciled and merged without force-pushing or rewriting the experiment history.

Merged release layers:

- PR #2 — Phase-1 engineering foundation;
- PR #3 — completed primary/PLOS/transfer evidence and reports;
- PR #4 — representative primary raw/resampled/filtered signal visualization discovered as missing during the final deliverable audit.

The final merged tree contains all original Issue #1 deliverables. The hardware decision remains **NOT YET** because the POC still lacks true same-person reinstallation evidence and retains material setup/time confounds.

Hosted CI is currently green on `main`: dependency installation, pytest, Ruff, and mypy all execute successfully. The repository also keeps heavy public-data research workflows manual and read-only; their generated metrics and plots are reviewed from workflow artifacts rather than pushed back automatically.
