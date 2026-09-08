from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_WORKFLOWS = (
    ".github/workflows/research-experiments.yml",
    ".github/workflows/research-primary.yml",
    ".github/workflows/research-probe.yml",
    ".github/workflows/research-transfer.yml",
)
RELEASE_DOCS = ("README.md", "docs/LOCAL_VALIDATION.md", "docs/PUSH_STATUS.md")


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_research_workflows_are_manual_read_only_artifact_jobs() -> None:
    for relative in RESEARCH_WORKFLOWS:
        text = _read(relative)
        assert "workflow_dispatch:" in text
        assert "\n  push:" not in text
        assert "contents: write" not in text
        assert "git push" not in text
        assert "git commit" not in text
        assert "contents: read" in text

    for relative in RESEARCH_WORKFLOWS:
        if relative.endswith("research-probe.yml"):
            continue
        assert "actions/upload-artifact@v4" in _read(relative)


def test_release_docs_do_not_contain_obsolete_ci_failure_claim() -> None:
    for relative in RELEASE_DOCS:
        assert "steps: null" not in _read(relative)


def test_transfer_artifact_contract_is_complete() -> None:
    age_predictions = ROOT / "metrics/transfer_28643153/age_predictions.csv"
    assert age_predictions.is_file()
    assert age_predictions.stat().st_size > 0
    assert "metrics/transfer_28643153/age_predictions.csv" in _read("reports/transfer.md")


def test_ci_uses_locked_cpu_only_torch_environment() -> None:
    ci = _read(".github/workflows/ci.yml")
    lock = _read("requirements/research-lock.txt")

    assert "requirements/research-lock.txt" in ci
    assert "download.pytorch.org/whl/cpu" in ci
    assert "git diff --check" in ci
    assert "torch==2.14.0" in lock
    assert "h5py==" in lock
    assert "nvidia-" not in lock.casefold()
