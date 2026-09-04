class SleepFingerprintError(RuntimeError):
    """Base error for expected pipeline failures."""


class DatasetError(SleepFingerprintError):
    """Dataset download, layout, checksum, or parsing failure."""


class SplitError(SleepFingerprintError):
    """A requested split cannot be made without leakage."""


class QualityError(SleepFingerprintError):
    """Signal quality or preprocessing failure."""
