from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

PRIMARY_DATASET_ID = "figshare:26013157/file:46976602"
PRIMARY_SENSOR_POSITION = "beneath mattress near chest"
PRIMARY_RECORDING_LOCATION = "participant dormitory sleeping environment"


@dataclass(frozen=True)
class InstallationAwareRecord:
    participant_id: str
    night_id: str | None
    session_id: str | None
    bed_id: str | None
    mattress_id: str | None
    sensor_id: str | None
    device_id: str | None
    installation_id: str | None
    sensor_position: str | None
    recording_location: str | None
    dataset_id: str
    recording_date: str | None
    source_path: str
    participant_id_provenance: str
    night_id_provenance: str | None
    session_id_provenance: str | None
    bed_id_provenance: str | None
    mattress_id_provenance: str | None
    sensor_id_provenance: str | None
    device_id_provenance: str | None
    installation_id_provenance: str | None
    sensor_position_provenance: str | None
    recording_location_provenance: str | None
    recording_date_provenance: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def primary_manifest_record(
    *,
    participant_id: str,
    night_id: str,
    source_path: str,
    recording_date: str | None,
) -> InstallationAwareRecord:
    return InstallationAwareRecord(
        participant_id=participant_id,
        night_id=night_id,
        session_id=None,
        bed_id=None,
        mattress_id=None,
        sensor_id=None,
        device_id=None,
        installation_id=None,
        sensor_position=PRIMARY_SENSOR_POSITION,
        recording_location=PRIMARY_RECORDING_LOCATION,
        dataset_id=PRIMARY_DATASET_ID,
        recording_date=recording_date,
        source_path=source_path,
        participant_id_provenance="source participant directory",
        night_id_provenance="source recording filename/date token; identifies a recording night only",
        session_id_provenance="unknown; recording night is not promoted to a session identifier",
        bed_id_provenance="unknown; not reported per record",
        mattress_id_provenance="unknown; not reported per record",
        sensor_id_provenance="unknown; sensor serial/device identity not reported per record",
        device_id_provenance="unknown; device identity not reported per record",
        installation_id_provenance=(
            "unknown; source does not report removal/reinstallation boundaries and night is not treated as installation"
        ),
        sensor_position_provenance=(
            "dataset paper protocol; dataset-level placement, not a per-night reinstallation record"
        ),
        recording_location_provenance="dataset paper protocol; dormitory natural-sleep environment",
        recording_date_provenance="source filename/date token" if recording_date else "unknown",
    )


def assert_installation_ids_are_source_backed(records: list[InstallationAwareRecord]) -> None:
    for record in records:
        if record.installation_id is None:
            continue
        provenance = (record.installation_id_provenance or "").strip().lower()
        if not provenance or any(token in provenance for token in ("night", "participant", "synthetic", "inferred")):
            raise ValueError(
                f"unsafe installation_id for {record.participant_id}/{record.night_id}: {record.installation_id!r}"
            )


def assert_evaluation_label_is_source_backed(
    records: list[InstallationAwareRecord],
    *,
    label_field: str,
) -> None:
    provenance_field = f"{label_field}_provenance"
    fields = InstallationAwareRecord.__dataclass_fields__
    if label_field not in fields:
        raise ValueError(f"unknown manifest label field: {label_field}")
    if provenance_field not in fields:
        raise ValueError(f"missing provenance column for label: {label_field}")
    for record in records:
        value = getattr(record, label_field)
        provenance = getattr(record, provenance_field)
        if value is None or value == "":
            raise ValueError(f"evaluation label {label_field} is unknown")
        if not provenance:
            raise ValueError(f"evaluation label {label_field} lacks provenance")
