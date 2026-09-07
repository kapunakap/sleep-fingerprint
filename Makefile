.DEFAULT_GOAL := help
PYTHON ?= python3.11

.PHONY: help test lint typecheck download extract audit baseline
help:
	@$(PYTHON) -m sleep_fingerprint --help

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

typecheck:
	$(PYTHON) -m mypy src

download:
	$(PYTHON) -m sleep_fingerprint download --data-dir data

extract:
	$(PYTHON) -m sleep_fingerprint extract --data-dir data --destination data/extracted

audit:
	$(PYTHON) -m sleep_fingerprint audit --dataset-root data/extracted --output-dir data/reports

baseline:
	$(PYTHON) -m sleep_fingerprint baseline --manifest data/reports/manifest.csv --splits data/reports/night_splits.json --dataset-root data/extracted --output-dir data/reports/baseline
