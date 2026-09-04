from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator

import numpy as np
from scipy.signal import butter, detrend, resample_poly, sosfiltfilt

from .errors import QualityError


@dataclass(frozen=True)
class PreprocessConfig:
    target_fs_hz: float = 64.0
    window_seconds: float = 60.0
    stride_seconds: float = 30.0
    respiratory_band_hz: tuple[float, float] = (0.08, 0.7)
    cardiac_band_hz: tuple[float, float] = (0.7, 15.0)

    @property
    def window_samples(self) -> int:
        return int(round(self.window_seconds * self.target_fs_hz))

    @property
    def stride_samples(self) -> int:
        return int(round(self.stride_seconds * self.target_fs_hz))


@dataclass(frozen=True)
class ProcessedWindow:
    start_sample: int
    end_sample: int
    respiratory: np.ndarray | None
    cardiac: np.ndarray | None
    accepted: bool
    reasons: tuple[str, ...]

    @property
    def signal(self) -> np.ndarray:
        if self.respiratory is None or self.cardiac is None:
            raise QualityError("rejected window has no model input")
        return np.stack([self.respiratory, self.cardiac]).astype(np.float32)


def resample_signal(signal: np.ndarray, source_fs_hz: float, target_fs_hz: float = 64.0) -> np.ndarray:
    values = np.asarray(signal, dtype=np.float64)
    if values.ndim != 1 or not values.size or not np.all(np.isfinite(values)):
        raise QualityError("resampling requires a finite 1D signal")
    ratio = Fraction(target_fs_hz / source_fs_hz).limit_denominator(10_000)
    return resample_poly(values, ratio.numerator, ratio.denominator, padtype="line")


def quality_reasons(values: np.ndarray) -> tuple[str, ...]:
    x = np.asarray(values, dtype=np.float64)
    reasons: list[str] = []
    if not x.size:
        return ("empty",)
    if not np.all(np.isfinite(x)):
        reasons.append("nonfinite")
        return tuple(reasons)
    if np.std(x) <= np.finfo(float).eps or np.ptp(x) <= np.finfo(float).eps:
        reasons.append("flatline")
    median = np.median(x)
    mad = np.median(np.abs(x - median))
    if mad > 0 and np.mean(np.abs(x - median) / (1.4826 * mad) > 20) > 0.01:
        reasons.append("excessive_outliers")
    minimum, maximum = np.min(x), np.max(x)
    if np.mean(np.isclose(x, minimum) | np.isclose(x, maximum)) > 0.02:
        reasons.append("possible_clipping")
    return tuple(reasons)


def separate_components(values: np.ndarray, config: PreprocessConfig) -> tuple[np.ndarray, np.ndarray]:
    x = detrend(np.asarray(values, dtype=np.float64), type="linear")
    median = np.median(x)
    mad = np.median(np.abs(x - median))
    scale = 1.4826 * mad
    if scale <= np.finfo(float).eps:
        raise QualityError("robust normalization scale is zero")
    x = (x - median) / scale
    resp = butter(4, config.respiratory_band_hz, btype="bandpass", fs=config.target_fs_hz, output="sos")
    cardiac = butter(4, config.cardiac_band_hz, btype="bandpass", fs=config.target_fs_hz, output="sos")
    return sosfiltfilt(resp, x), sosfiltfilt(cardiac, x)


def iter_night_windows(
    signal: np.ndarray,
    source_fs_hz: float,
    config: PreprocessConfig | None = None,
) -> Iterator[ProcessedWindow]:
    active = config or PreprocessConfig()
    resampled = resample_signal(signal, source_fs_hz, active.target_fs_hz)
    for start in range(0, resampled.size - active.window_samples + 1, active.stride_samples):
        end = start + active.window_samples
        segment = resampled[start:end]
        reasons = quality_reasons(segment)
        if reasons:
            yield ProcessedWindow(start, end, None, None, False, reasons)
            continue
        try:
            respiratory, cardiac = separate_components(segment, active)
        except QualityError as error:
            yield ProcessedWindow(start, end, None, None, False, (str(error),))
            continue
        yield ProcessedWindow(start, end, respiratory, cardiac, True, ())
