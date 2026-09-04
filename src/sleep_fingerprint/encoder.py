from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F


@dataclass(frozen=True)
class EncoderConfig:
    input_channels: int = 2
    embedding_dim: int = 256
    base_channels: int = 32
    dropout: float = 0.1


class ResidualBlock(nn.Module):
    def __init__(self, channels: int, dropout: float) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.BatchNorm1d(channels),
            nn.GELU(),
            nn.Conv1d(channels, channels, 5, padding=2, bias=False),
            nn.BatchNorm1d(channels),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Conv1d(channels, channels, 3, padding=1, bias=False),
        )

    def forward(self, values: Tensor) -> Tensor:
        return values + self.body(values)


class SleepFingerprintEncoder(nn.Module):
    def __init__(self, config: EncoderConfig | None = None) -> None:
        super().__init__()
        self.config = config or EncoderConfig()
        width = self.config.base_channels
        self.network = nn.Sequential(
            nn.Conv1d(2, width, 9, stride=2, padding=4, bias=False),
            ResidualBlock(width, self.config.dropout),
            nn.Conv1d(width, width * 2, 5, stride=2, padding=2, bias=False),
            ResidualBlock(width * 2, self.config.dropout),
            nn.Conv1d(width * 2, width * 4, 5, stride=2, padding=2, bias=False),
            ResidualBlock(width * 4, self.config.dropout),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(width * 4, self.config.embedding_dim),
        )

    def forward(self, values: Tensor) -> Tensor:
        if values.ndim != 3 or values.shape[1] != 2:
            raise ValueError("encoder expects [batch, 2, samples]")
        return F.normalize(self.network(values), p=2, dim=1, eps=1e-12)


@dataclass(frozen=True)
class WindowRecord:
    relative_path: str
    subject_id: str
    night_key: str


@dataclass(frozen=True)
class PairSample:
    anchor: WindowRecord
    positive: WindowRecord


class CrossNightPairSampler:
    def __init__(self, records: Sequence[WindowRecord], seed: int = 0) -> None:
        self.rng = np.random.default_rng(seed)
        self.by_subject: dict[str, dict[str, list[WindowRecord]]] = {}
        for record in records:
            self.by_subject.setdefault(record.subject_id, {}).setdefault(record.night_key, []).append(record)
        self.eligible = tuple(sorted(subject for subject, nights in self.by_subject.items() if len(nights) >= 2))
        if not self.eligible:
            raise ValueError("cross-night positives require at least two nights for one subject")

    def sample_pair(self) -> PairSample:
        subject = self.eligible[int(self.rng.integers(0, len(self.eligible)))]
        nights = tuple(sorted(self.by_subject[subject]))
        first, second = self.rng.choice(len(nights), size=2, replace=False)
        a_night, p_night = nights[int(first)], nights[int(second)]
        anchor_pool, positive_pool = self.by_subject[subject][a_night], self.by_subject[subject][p_night]
        anchor = anchor_pool[int(self.rng.integers(0, len(anchor_pool)))]
        positive = positive_pool[int(self.rng.integers(0, len(positive_pool)))]
        assert anchor.subject_id == positive.subject_id
        assert anchor.night_key != positive.night_key
        return PairSample(anchor, positive)
