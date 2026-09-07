# Local validation

The completed Issue #1 tree has been exercised with the real project environment, not only synthetic inspection.

Final closeout software validation:

```text
pytest
→ 26 passed

ruff check src tests scripts
→ All checks passed!

mypy src
→ Success: no issues found in 14 source files

git diff --check
→ passed
```

A clean Python 3.11 bootstrap also succeeded with:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,encoder]'
```

Scientific execution is recorded separately in the committed metrics/reports. In particular, the post-parser-fix 212-night primary package and the fresh PLOS cross-sensor run both completed successfully.

GitHub Actions **is configured**, but the fresh closeout runs observed during release failed before a runner/workflow step was assigned (`steps: null`). That is a hosted Actions runner/startup infrastructure failure: it is neither a green hosted run nor a code-executed test failure. The executed local validation above is therefore recorded explicitly.
