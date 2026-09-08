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

A clean Python 3.11 bootstrap also succeeded. Reproducible QA/research installs now use `requirements/research-lock.txt` as a constraints file. Linux CI installs the CPU-only PyTorch wheel explicitly before the locked project environment so encoder tests do not pull the CUDA dependency stack.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "torch==2.14.0" --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e '.[dev,encoder]' -c requirements/research-lock.txt
python -m pip check
```

Scientific execution is recorded separately in the committed metrics/reports. In particular, the post-parser-fix 212-night primary package and the fresh PLOS cross-sensor run both completed successfully.

Hosted GitHub Actions on `main` is currently green: environment installation, pytest, Ruff, and mypy all execute successfully. Heavy research workflows are manual-only and read-only with respect to repository contents; generated research outputs are exported as workflow artifacts for review instead of being committed automatically.
