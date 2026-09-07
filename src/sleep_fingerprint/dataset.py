from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

from .errors import DatasetError

FIGSHARE_ARTICLE_ID = 26013157
FIGSHARE_FILE_ID = 46976602
FIGSHARE_API_URL = f"https://api.figshare.com/v2/articles/{FIGSHARE_ARTICLE_ID}"
FIGSHARE_DOWNLOAD_URL = f"https://ndownloader.figshare.com/files/{FIGSHARE_FILE_ID}"
EXPECTED_ARCHIVE_NAME = "dataset.zip"
EXPECTED_ARCHIVE_BYTES = 1_624_767_747
EXPECTED_ARCHIVE_MD5 = "5f1b50277e000a56b2b8d3df4f6ad81c"
UTC_PLUS_8 = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class ParsedBCG:
    signal: np.ndarray
    source_fs_hz: float
    start_timestamp_utc_plus_08: str | None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManifestRecord:
    subject_id: str
    night_key: str
    night_date: str
    source_path: str
    sample_count: int
    duration_seconds: float
    source_fs_hz: float
    start_timestamp_utc_plus_08: str | None
    has_reference_rr: bool
    has_reference_resp: bool
    age: float | None = None


def hash_file(path: Path, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(
    path: Path,
    expected_bytes: int = EXPECTED_ARCHIVE_BYTES,
    expected_md5: str = EXPECTED_ARCHIVE_MD5,
) -> dict[str, Any]:
    if not path.is_file():
        raise DatasetError(f"archive missing: {path}")
    size = path.stat().st_size
    if size != expected_bytes:
        raise DatasetError(f"archive size mismatch: expected {expected_bytes}, got {size}")
    md5 = hash_file(path)
    if md5.lower() != expected_md5.lower():
        raise DatasetError(f"archive MD5 mismatch: expected {expected_md5}, got {md5}")
    return {"bytes": size, "md5": md5, "verified_at_utc": datetime.now(UTC).isoformat()}


def fetch_figshare_metadata() -> dict[str, Any]:
    response = requests.get(FIGSHARE_API_URL, timeout=30)
    response.raise_for_status()
    article = response.json()
    target = next((f for f in article.get("files", []) if int(f.get("id", -1)) == FIGSHARE_FILE_ID), None)
    if not target:
        raise DatasetError("pinned Figshare file not present in article metadata")
    if int(target.get("size", -1)) != EXPECTED_ARCHIVE_BYTES:
        raise DatasetError("Figshare file size no longer matches pinned dataset identity")
    if str(target.get("supplied_md5", "")).lower() != EXPECTED_ARCHIVE_MD5:
        raise DatasetError("Figshare MD5 no longer matches pinned dataset identity")
    return {"article": article, "file": target}


def download_dataset(data_dir: Path) -> tuple[Path, dict[str, Any]]:
    metadata = fetch_figshare_metadata()
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive = raw_dir / EXPECTED_ARCHIVE_NAME
    partial = raw_dir / f"{EXPECTED_ARCHIVE_NAME}.part"
    if archive.exists():
        return archive, verify_archive(archive)

    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    url = str(metadata["file"].get("download_url") or FIGSHARE_DOWNLOAD_URL)
    response = requests.get(url, headers=headers, stream=True, timeout=(30, 120))
    response.raise_for_status()
    append = offset > 0 and response.status_code == 206
    if offset and not append:
        offset = 0
    mode = "ab" if append else "wb"
    total_header = response.headers.get("content-length")
    total = offset + int(total_header) if total_header and total_header.isdigit() else None
    with partial.open(mode) as handle, tqdm(total=total, initial=offset, unit="B", unit_scale=True) as bar:
        for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
            if chunk:
                handle.write(chunk)
                bar.update(len(chunk))
    verification = verify_archive(partial)
    os.replace(partial, archive)
    provenance = {
        "article_id": FIGSHARE_ARTICLE_ID,
        "file_id": FIGSHARE_FILE_ID,
        "download_url": response.url,
        "license": (metadata["article"].get("license") or {}).get("name"),
        "verification": verification,
    }
    (data_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return archive, verification


def sanitize_zip_member(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if not normalized or candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise DatasetError(f"unsafe zip member: {name!r}")
    if candidate.parts and ":" in candidate.parts[0]:
        raise DatasetError(f"unsafe zip member: {name!r}")
    return candidate


def safe_extract_zip(archive: Path, destination: Path) -> dict[str, int]:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        for info in source.infolist():
            member = sanitize_zip_member(info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise DatasetError(f"refusing symlink in archive: {info.filename}")
            members.append((info, member))
        uncompressed = sum(info.file_size for info, _ in members)
        if shutil.disk_usage(destination).free < int(uncompressed * 1.15) + 2 * 1024**3:
            raise DatasetError("insufficient free disk for guarded extraction")
        root = destination.resolve()
        for info, member in tqdm(members, unit="file", desc="extracting"):
            target = destination.joinpath(*member.parts)
            try:
                target.resolve().relative_to(root)
            except ValueError as error:
                raise DatasetError(f"unsafe extraction target: {info.filename}") from error
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as src, tempfile.NamedTemporaryFile(delete=False, dir=target.parent) as tmp:
                temp = Path(tmp.name)
                shutil.copyfileobj(src, tmp)
            os.replace(temp, target)
    return {"members": len(members), "uncompressed_bytes": uncompressed}


def _unix_to_local(value: float) -> str | None:
    try:
        moment = pd.to_datetime(value, unit="s", utc=True)
    except (OverflowError, ValueError):
        return None
    if not 2000 <= moment.year <= 2100:
        return None
    return moment.tz_convert(UTC_PLUS_8).isoformat()


def parse_bcg_csv(path: Path, default_fs_hz: float = 140.0) -> ParsedBCG:
    values: list[float] = []
    fs_values: list[float] = []
    first_timestamp: float | None = None
    saw_body = False
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            row = [*row[:3], *("" for _ in range(max(0, 3 - len(row))))]
            text = row[0].strip()
            if not text:
                if saw_body:
                    raise DatasetError(f"empty BCG value at line {line_number}")
                continue
            try:
                value = float(text)
            except ValueError as error:
                if not saw_body and any(token in text.casefold() for token in ("bcg", "signal", "value", "data")):
                    continue
                raise DatasetError(f"malformed BCG value at line {line_number}") from error
            if not np.isfinite(value):
                raise DatasetError(f"non-finite BCG value at line {line_number}")
            saw_body = True
            values.append(value)
            if row[1].strip() and first_timestamp is None:
                try:
                    first_timestamp = float(row[1])
                except ValueError:
                    pass
            if row[2].strip():
                try:
                    fs = float(row[2])
                except ValueError:
                    continue
                if np.isfinite(fs) and fs > 0:
                    fs_values.append(fs)
    if not values:
        raise DatasetError(f"BCG CSV is empty: {path.name}")
    fs = float(np.median(fs_values)) if fs_values else float(default_fs_hz)
    if not 1 <= fs <= 2000:
        raise DatasetError(f"implausible BCG sampling frequency: {fs}")
    return ParsedBCG(
        signal=np.asarray(values, dtype=np.float64),
        source_fs_hz=fs,
        start_timestamp_utc_plus_08=_unix_to_local(first_timestamp) if first_timestamp is not None else None,
        diagnostics=() if fs_values else ("sampling rate absent; explicit 140 Hz default used",),
    )


def _date_from_name(name: str) -> str | None:
    for token in name.replace("-", "_").split("_"):
        if len(token) == 8 and token.isdigit():
            return token
    return None


def discover_bcg_files(dataset_root: Path) -> list[tuple[str, str, Path]]:
    discovered: list[tuple[str, str, Path]] = []
    for path in sorted(dataset_root.rglob("*_BCG.csv")):
        if path.parent.name.casefold() != "bcg":
            continue
        subject = path.parent.parent.name
        date = _date_from_name(path.stem)
        if date:
            discovered.append((subject, date, path))
    if not discovered:
        raise DatasetError("no BCG files discovered")
    return discovered


def _subject_ages(dataset_root: Path) -> dict[str, float]:
    files = list(dataset_root.rglob("subject_info.csv"))
    if not files:
        return {}
    table = pd.read_csv(files[0], encoding="utf-8-sig")
    columns = {str(c).strip().lower(): c for c in table.columns}
    id_col = next((columns[k] for k in columns if k in {"id", "subject id", "subject_id", "subjectid"}), None)
    age_col = next((columns[k] for k in columns if k == "age"), None)
    if id_col is None or age_col is None:
        return {}
    out: dict[str, float] = {}
    for _, row in table.iterrows():
        try:
            out[str(row[id_col]).strip()] = float(row[age_col])
        except (TypeError, ValueError):
            continue
    return out


def audit_dataset(dataset_root: Path) -> tuple[list[ManifestRecord], dict[str, Any], list[dict[str, str]]]:
    ages = _subject_ages(dataset_root)
    records: list[ManifestRecord] = []
    bad: list[dict[str, str]] = []
    for subject, date, path in discover_bcg_files(dataset_root):
        relative = path.resolve().relative_to(dataset_root.resolve()).as_posix()
        try:
            parsed = parse_bcg_csv(path)
        except DatasetError as error:
            bad.append({"source_path": relative, "reason": str(error)})
            continue
        reference = path.parent.parent / "Reference"
        rr = (
            any(
                _date_from_name(p.name) == date
                for p in reference.rglob("*")
                if p.is_file() and p.parent.name.lower() == "rr"
            )
            if reference.exists()
            else False
        )
        resp = (
            any(
                _date_from_name(p.name) == date
                for p in reference.rglob("*")
                if p.is_file() and p.parent.name.lower() == "resp"
            )
            if reference.exists()
            else False
        )
        records.append(
            ManifestRecord(
                subject_id=subject,
                night_key=f"{subject}:{date}",
                night_date=date,
                source_path=relative,
                sample_count=len(parsed.signal),
                duration_seconds=len(parsed.signal) / parsed.source_fs_hz,
                source_fs_hz=parsed.source_fs_hz,
                start_timestamp_utc_plus_08=parsed.start_timestamp_utc_plus_08,
                has_reference_rr=rr,
                has_reference_resp=resp,
                age=ages.get(subject),
            )
        )
    counts = Counter(r.subject_id for r in records)
    stats = {
        "subjects": len(counts),
        "valid_nights": len(records),
        "bad_records": len(bad),
        "nights_per_subject_min": min(counts.values()) if counts else 0,
        "nights_per_subject_median": float(np.median(list(counts.values()))) if counts else 0.0,
        "nights_per_subject_max": max(counts.values()) if counts else 0,
        "source_fs_hz": dict(Counter(f"{r.source_fs_hz:g}" for r in records)),
        "age_min": min((r.age for r in records if r.age is not None), default=None),
        "age_max": max((r.age for r in records if r.age is not None), default=None),
    }
    return records, stats, bad


def write_audit(
    records: list[ManifestRecord],
    stats: dict[str, Any],
    bad: list[dict[str, str]],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = [asdict(record) for record in records]
    pd.DataFrame(payload).to_csv(output_dir / "manifest.csv", index=False)
    (output_dir / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n")
    (output_dir / "audit.json").write_text(json.dumps({"statistics": stats, "bad_records": bad}, indent=2) + "\n")
