from __future__ import annotations

from sleep_fingerprint.primary_experiment import make_chronological_half_split, summarize_split


def test_chronological_half_split_reproduces_64_54_query_layout() -> None:
    records: list[dict[str, str]] = []
    subject = 0
    for nights, participant_count in ((5, 2), (6, 8), (7, 22)):
        for _ in range(participant_count):
            subject += 1
            for night in range(nights):
                records.append(
                    {
                        "subject_id": f"P{subject:02d}",
                        "night_key": f"P{subject:02d}:202601{night + 1:02d}",
                        "night_date": f"202601{night + 1:02d}",
                        "source_path": f"P{subject:02d}/BCG/{night}.csv",
                    }
                )
    split = make_chronological_half_split(records)
    assert summarize_split(split) == {
        "train_nights": 94,
        "val_nights": 64,
        "test_nights": 54,
        "subjects": 32,
        "exclusions": [],
    }


def test_chronological_split_is_ordered_and_night_disjoint() -> None:
    records = [
        {
            "subject_id": "P01",
            "night_key": f"P01:202601{night:02d}",
            "night_date": f"202601{night:02d}",
            "source_path": f"P01/BCG/{night}.csv",
        }
        for night in range(1, 8)
    ]
    split = make_chronological_half_split(reversed(records))
    assignments = sorted(split.assignments, key=lambda item: item.night_key)
    assert [assignment.split for assignment in assignments] == [
        "train",
        "train",
        "train",
        "val",
        "val",
        "test",
        "test",
    ]
    keys = [assignment.night_key for assignment in assignments]
    assert len(keys) == len(set(keys))
