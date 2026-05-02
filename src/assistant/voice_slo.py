from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from statistics import median
from typing import Sequence


@dataclass(frozen=True)
class VoiceLatencySample:
    stt_ms: float
    orchestrator_ms: float
    tts_ms: float
    network_ms: float = 0.0

    @property
    def e2e_ms(self) -> float:
        return self.stt_ms + self.orchestrator_ms + self.tts_ms + self.network_ms


def compute_latency_summary(samples: Sequence[VoiceLatencySample]) -> dict[str, float]:
    if not samples:
        raise ValueError("samples ne peut pas etre vide")

    e2e = [sample.e2e_ms for sample in samples]
    e2e_sorted = sorted(e2e)
    idx_95 = min(len(e2e_sorted) - 1, max(0, ceil(0.95 * len(e2e_sorted)) - 1))

    return {
        "sample_count": float(len(samples)),
        "median_e2e_ms": median(e2e),
        "p95_e2e_ms": e2e_sorted[idx_95],
        "max_e2e_ms": max(e2e),
    }


def validate_e2e_latency_slo(
    samples: Sequence[VoiceLatencySample], *, max_median_ms: float = 1800.0
) -> bool:
    summary = compute_latency_summary(samples)
    return summary["median_e2e_ms"] <= max_median_ms
