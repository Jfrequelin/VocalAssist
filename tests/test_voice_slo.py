from __future__ import annotations

import unittest

from src.assistant.voice_slo import (
    VoiceLatencySample,
    compute_latency_summary,
    validate_e2e_latency_slo,
)


class TestVoiceSLO(unittest.TestCase):
    def test_compute_latency_summary(self) -> None:
        samples = [
            VoiceLatencySample(stt_ms=350, orchestrator_ms=120, tts_ms=420, network_ms=180),
            VoiceLatencySample(stt_ms=390, orchestrator_ms=130, tts_ms=450, network_ms=170),
            VoiceLatencySample(stt_ms=410, orchestrator_ms=140, tts_ms=470, network_ms=160),
        ]

        summary = compute_latency_summary(samples)
        self.assertEqual(summary["sample_count"], 3.0)
        self.assertLess(summary["median_e2e_ms"], 1800.0)
        self.assertGreater(summary["p95_e2e_ms"], 0.0)

    def test_validate_e2e_latency_slo_ok(self) -> None:
        samples = [
            VoiceLatencySample(stt_ms=320, orchestrator_ms=110, tts_ms=430, network_ms=170),
            VoiceLatencySample(stt_ms=340, orchestrator_ms=120, tts_ms=410, network_ms=190),
            VoiceLatencySample(stt_ms=360, orchestrator_ms=130, tts_ms=400, network_ms=170),
            VoiceLatencySample(stt_ms=380, orchestrator_ms=130, tts_ms=430, network_ms=160),
            VoiceLatencySample(stt_ms=400, orchestrator_ms=140, tts_ms=420, network_ms=170),
        ]
        self.assertTrue(validate_e2e_latency_slo(samples, max_median_ms=1800.0))

    def test_validate_e2e_latency_slo_ko(self) -> None:
        samples = [
            VoiceLatencySample(stt_ms=800, orchestrator_ms=400, tts_ms=500, network_ms=300),
            VoiceLatencySample(stt_ms=900, orchestrator_ms=400, tts_ms=500, network_ms=300),
            VoiceLatencySample(stt_ms=950, orchestrator_ms=420, tts_ms=520, network_ms=320),
        ]
        self.assertFalse(validate_e2e_latency_slo(samples, max_median_ms=1800.0))

    def test_summary_rejects_empty_samples(self) -> None:
        with self.assertRaises(ValueError):
            compute_latency_summary([])


if __name__ == "__main__":
    unittest.main()
