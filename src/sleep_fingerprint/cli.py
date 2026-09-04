from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .baseline import run_handcrafted_baseline
from .dataset import EXPECTED_ARCHIVE_NAME, audit_dataset, download_dataset, safe_extract_zip, verify_archive, write_audit
from .errors import SleepFingerprintError
from .split import load_splits, make_night_splits, write_splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sleep-fingerprint")
    commands = parser.add_subparsers(dest="command", required=True)

    download = commands.add_parser("download")
    download.add_argument("--data-dir", type=Path, default=Path("data"))

    extract = commands.add_parser("extract")
    extract.add_argument("--data-dir", type=Path, default=Path("data"))
    extract.add_argument("--destination", type=Path, default=Path("data/extracted"))

    audit = commands.add_parser("audit")
    audit.add_argument("--dataset-root", type=Path, required=True)
    audit.add_argument("--output-dir", type=Path, default=Path("data/reports"))
    audit.add_argument("--seed", type=int, default=20260904)

    baseline = commands.add_parser("baseline")
    baseline.add_argument("--manifest", type=Path, required=True)
    baseline.add_argument("--splits", type=Path, required=True)
    baseline.add_argument("--dataset-root", type=Path, required=True)
    baseline.add_argument("--output-dir", type=Path, required=True)
    baseline.add_argument("--max-windows-per-night", type=int, default=12)

    args = parser.parse_args(argv)
    try:
        if args.command == "download":
            archive, verification = download_dataset(args.data_dir)
            print(json.dumps({"archive": str(archive), "verification": verification}, indent=2))
        elif args.command == "extract":
            archive = args.data_dir / "raw" / EXPECTED_ARCHIVE_NAME
            verify_archive(archive)
            print(json.dumps(safe_extract_zip(archive, args.destination), indent=2))
        elif args.command == "audit":
            records, stats, bad = audit_dataset(args.dataset_root)
            write_audit(records, stats, bad, args.output_dir)
            split = make_night_splits([asdict(record) for record in records], seed=args.seed)
            write_splits(split, args.output_dir / "night_splits.json")
            print(json.dumps({"statistics": stats, "excluded_subjects": len(split.exclusions)}, indent=2))
        elif args.command == "baseline":
            manifest = pd.read_csv(args.manifest).to_dict(orient="records")
            results = run_handcrafted_baseline(
                manifest,
                load_splits(args.splits),
                args.dataset_root,
                args.max_windows_per_night,
            )
            args.output_dir.mkdir(parents=True, exist_ok=True)
            payload = {split: result.metrics for split, result in results.items()}
            (args.output_dir / "baseline_summary.json").write_text(json.dumps(payload, indent=2) + "\n")
            print(json.dumps(payload, indent=2))
    except (SleepFingerprintError, ValueError, OSError) as error:
        parser.exit(2, f"sleep-fingerprint: error: {error}\n")
    return 0
