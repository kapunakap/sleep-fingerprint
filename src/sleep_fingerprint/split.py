from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .errors import SplitError


@dataclass(frozen=True)
class NightAssignment:
    subject_id: str
    night_key: str
    split: str
    source_path: str | None = None


@dataclass(frozen=True)
class SplitResult:
    seed: int
    assignments: tuple[NightAssignment, ...]
    exclusions: tuple[dict[str, Any], ...]

    def by_night(self) -> dict[str, str]:
        return {item.night_key: item.split for item in self.assignments}


def _rng(seed: int, subject: str) -> np.random.Generator:
    material = hashlib.sha256(f"{seed}:{subject}".encode()).digest()[:8]
    return np.random.default_rng(int.from_bytes(material, "big"))


def make_night_splits(records: Iterable[Mapping[str, Any]], seed: int = 20260904) -> SplitResult:
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_subject[str(record["subject_id"])].append(dict(record))
    assignments: list[NightAssignment] = []
    exclusions: list[dict[str, Any]] = []
    for subject in sorted(by_subject):
        nights = sorted(by_subject[subject], key=lambda x: str(x["night_key"]))
        if len(nights) < 3:
            exclusions.append({"subject_id": subject, "nights": len(nights), "reason": "needs >=3 nights"})
            continue
        shuffled = [nights[i] for i in _rng(seed, subject).permutation(len(nights))]
        train_count = max(1, len(nights) - 2)
        layout = ["train"] * train_count + ["val", "test"]
        for record, split in zip(shuffled, layout, strict=True):
            assignments.append(
                NightAssignment(subject, str(record["night_key"]), split, str(record.get("source_path") or ""))
            )
    seen: dict[str, str] = {}
    for assignment in assignments:
        previous = seen.setdefault(assignment.night_key, assignment.split)
        if previous != assignment.split:
            raise SplitError(f"night leakage: {assignment.night_key}")
    return SplitResult(seed, tuple(sorted(assignments, key=lambda x: (x.subject_id, x.night_key))), tuple(exclusions))


def write_splits(result: SplitResult, path: Path) -> None:
    payload = {
        "split_unit": "night",
        "seed": result.seed,
        "assignments": [asdict(x) for x in result.assignments],
        "exclusions": list(result.exclusions),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def load_splits(path: Path) -> SplitResult:
    payload = json.loads(path.read_text())
    if payload.get("split_unit") != "night":
        raise SplitError("split file does not declare night as atomic unit")
    return SplitResult(
        int(payload["seed"]),
        tuple(NightAssignment(**x) for x in payload.get("assignments", [])),
        tuple(payload.get("exclusions", [])),
    )
