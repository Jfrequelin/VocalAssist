"""Tests d'observabilité: KPI, tracing corrélé, alertes provider/Leon.

Critères ticket #307:
- KPI exposés pour au moins 3 parcours de démo (light, meteo, timer)
- Corrélation traçable de bout en bout sur 10 interactions
- Alertes testées sur panne provider et panne Leon
"""
from __future__ import annotations

import unittest
import uuid

from src.assistant.observability import (
    Alert,
    AlertManager,
    InteractionTrace,
    KpiSummary,
    MetricsCollector,
)


def _cid() -> str:
    return str(uuid.uuid4())


class TestMetricsCollector(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = MetricsCollector()

    # -- Enregistrement -------------------------------------------------------

    def test_record_interaction_adds_trace(self) -> None:
        cid = _cid()
        trace = self.collector.record_interaction(
            correlation_id=cid, intent="light", route="local",
            stt_ms=120.0, orchestrator_ms=30.0, tts_ms=200.0, success=True,
        )
        self.assertEqual(len(self.collector.all_traces()), 1)
        self.assertEqual(trace.correlation_id, cid)
        self.assertAlmostEqual(trace.e2e_ms, 350.0)

    def test_10_interactions_all_traceable_by_correlation_id(self) -> None:
        """Corrélation traçable de bout en bout sur 10 interactions."""
        cids = [_cid() for _ in range(10)]
        for cid in cids:
            self.collector.record_interaction(
                correlation_id=cid, intent="light", route="local",
                stt_ms=100.0, orchestrator_ms=20.0, tts_ms=180.0, success=True,
            )
        self.assertEqual(len(self.collector.unique_correlation_ids()), 10)
        for cid in cids:
            traces = self.collector.traces_for_correlation(cid)
            self.assertEqual(len(traces), 1)
            self.assertEqual(traces[0].correlation_id, cid)

    def test_reset_clears_all_traces(self) -> None:
        self.collector.record_interaction(
            correlation_id=_cid(), intent="light", route="local", success=True
        )
        self.collector.reset()
        self.assertEqual(len(self.collector.all_traces()), 0)

    # -- KPI vides ------------------------------------------------------------

    def test_kpi_summary_no_traces_returns_zero_defaults(self) -> None:
        kpi = self.collector.kpi_summary()
        self.assertEqual(kpi.total_interactions, 0)
        self.assertEqual(kpi.success_rate, 0.0)

    # -- KPI 3 parcours de démo -----------------------------------------------

    def _populate_3_parcours(self) -> None:
        """Peuple le collecteur avec 3 parcours: light, meteo, timer."""
        for _ in range(4):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local",
                stt_ms=120.0, orchestrator_ms=25.0, tts_ms=180.0, success=True,
            )
        for _ in range(3):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="meteo", route="local",
                stt_ms=140.0, orchestrator_ms=35.0, tts_ms=200.0, success=True,
            )
        for _ in range(3):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="timer", route="local",
                stt_ms=100.0, orchestrator_ms=20.0, tts_ms=160.0, success=True,
            )

    def test_kpi_covers_3_demo_parcours(self) -> None:
        """KPI exposés pour au moins 3 parcours de démo."""
        self._populate_3_parcours()
        kpi = self.collector.kpi_summary()
        self.assertEqual(kpi.total_interactions, 10)
        self.assertEqual(kpi.success_count, 10)
        self.assertAlmostEqual(kpi.success_rate, 1.0)
        self.assertIn("light", kpi.intent_distribution)
        self.assertIn("meteo", kpi.intent_distribution)
        self.assertIn("timer", kpi.intent_distribution)
        self.assertGreater(kpi.median_e2e_ms, 0)
        self.assertGreater(kpi.p95_e2e_ms, 0)

    def test_kpi_for_parcours_light(self) -> None:
        self._populate_3_parcours()
        kpi = self.collector.kpi_for_parcours("light")
        self.assertEqual(kpi.total_interactions, 4)
        self.assertAlmostEqual(kpi.success_rate, 1.0)

    def test_kpi_for_parcours_meteo(self) -> None:
        self._populate_3_parcours()
        kpi = self.collector.kpi_for_parcours("meteo")
        self.assertEqual(kpi.total_interactions, 3)

    def test_kpi_for_parcours_timer(self) -> None:
        self._populate_3_parcours()
        kpi = self.collector.kpi_for_parcours("timer")
        self.assertEqual(kpi.total_interactions, 3)

    # -- KPI avec erreurs -----------------------------------------------------

    def test_kpi_counts_failures_correctly(self) -> None:
        for _ in range(8):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local", success=True
            )
        for _ in range(2):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="error",
                success=False, error_type="provider_failure",
            )
        kpi = self.collector.kpi_summary()
        self.assertEqual(kpi.success_count, 8)
        self.assertEqual(kpi.failure_count, 2)
        self.assertAlmostEqual(kpi.success_rate, 0.8)
        self.assertEqual(kpi.provider_failure_count, 2)

    # -- Export Prometheus ----------------------------------------------------

    def test_export_prometheus_text_contains_required_metrics(self) -> None:
        self._populate_3_parcours()
        text = self.collector.export_prometheus_text()
        self.assertIn("interactions_total 10", text)
        self.assertIn("interactions_success_total 10", text)
        self.assertIn("interactions_failure_total 0", text)
        self.assertIn("success_rate 1.0000", text)
        self.assertIn("e2e_latency_ms_median", text)
        self.assertIn("e2e_latency_ms_p95", text)
        self.assertIn('routing_total{route="local"}', text)


class TestAlertManager(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = MetricsCollector()
        self.alerts = AlertManager(
            self.collector,
            max_failure_rate=0.20,
            max_p95_latency_ms=2500.0,
            max_leon_failure_rate=0.10,
            max_provider_failure_rate=0.10,
            min_interactions_for_alert=3,
        )

    # -- Système sain --------------------------------------------------------

    def test_no_alerts_when_all_ok(self) -> None:
        for _ in range(10):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local",
                stt_ms=100.0, orchestrator_ms=20.0, tts_ms=200.0, success=True,
            )
        self.assertEqual(self.alerts.check_all(), [])
        self.assertTrue(self.alerts.is_healthy())

    def test_no_alerts_below_min_interactions(self) -> None:
        """Pas d'alerte si moins de min_interactions_for_alert traces."""
        self.collector.record_interaction(
            correlation_id=_cid(), intent="light", route="error",
            success=False, error_type="provider_failure",
        )
        self.assertEqual(self.alerts.check_all(), [])

    # -- Alerte panne provider -----------------------------------------------

    def test_alert_raised_on_provider_failure(self) -> None:
        """Alerte testée sur panne provider (critère #307)."""
        for _ in range(7):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local", success=True
            )
        for _ in range(3):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="error",
                success=False, error_type="provider_failure",
            )
        active = self.alerts.check_all()
        names = [a.name for a in active]
        self.assertIn("provider_unavailable", names)
        alert = next(a for a in active if a.name == "provider_unavailable")
        self.assertEqual(alert.level, "critical")
        self.assertGreater(alert.value, self.alerts.max_provider_failure_rate)

    def test_no_provider_alert_below_threshold(self) -> None:
        for _ in range(10):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local", success=True
            )
        self.collector.record_interaction(
            correlation_id=_cid(), intent="light", route="error",
            success=False, error_type="provider_failure",
        )
        names = [a.name for a in self.alerts.check_all()]
        self.assertNotIn("provider_unavailable", names)

    # -- Alerte panne Leon ---------------------------------------------------

    def test_alert_raised_on_leon_failure(self) -> None:
        """Alerte testée sur panne Leon (critère #307)."""
        for _ in range(7):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local", success=True
            )
        for _ in range(3):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="error",
                success=False, error_type="leon_failure",
            )
        active = self.alerts.check_all()
        names = [a.name for a in active]
        self.assertIn("leon_unavailable", names)
        alert = next(a for a in active if a.name == "leon_unavailable")
        self.assertEqual(alert.level, "critical")

    def test_no_leon_alert_below_threshold(self) -> None:
        for _ in range(20):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local", success=True
            )
        self.collector.record_interaction(
            correlation_id=_cid(), intent="light", route="error",
            success=False, error_type="leon_failure",
        )
        names = [a.name for a in self.alerts.check_all()]
        self.assertNotIn("leon_unavailable", names)

    # -- Alerte taux d'échec global ------------------------------------------

    def test_alert_on_high_failure_rate(self) -> None:
        for _ in range(5):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local", success=True
            )
        for _ in range(5):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="error",
                success=False, error_type="timeout",
            )
        names = [a.name for a in self.alerts.check_all()]
        self.assertIn("high_failure_rate", names)

    # -- Alerte latence P95 --------------------------------------------------

    def test_alert_on_high_p95_latency(self) -> None:
        # 2 rapides (320ms) + 2 lentes (2700ms) → P95 = index 2 = 2700ms
        for _ in range(2):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local",
                stt_ms=100.0, orchestrator_ms=20.0, tts_ms=200.0, success=True,
            )
        for _ in range(2):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local",
                stt_ms=1000.0, orchestrator_ms=500.0, tts_ms=1200.0, success=True,
            )
        names = [a.name for a in self.alerts.check_all()]
        self.assertIn("high_p95_latency", names)

    def test_no_latency_alert_within_threshold(self) -> None:
        for _ in range(10):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local",
                stt_ms=100.0, orchestrator_ms=20.0, tts_ms=200.0, success=True,
            )
        names = [a.name for a in self.alerts.check_all()]
        self.assertNotIn("high_p95_latency", names)

    # -- Cumul d'alertes -----------------------------------------------------

    def test_multiple_alerts_can_fire_simultaneously(self) -> None:
        """Leon + provider en panne simultanément."""
        for _ in range(4):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="local", success=True
            )
        for _ in range(2):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="error",
                success=False, error_type="leon_failure",
            )
        for _ in range(2):
            self.collector.record_interaction(
                correlation_id=_cid(), intent="light", route="error",
                success=False, error_type="provider_failure",
            )
        active = self.alerts.check_all()
        names = [a.name for a in active]
        self.assertIn("leon_unavailable", names)
        self.assertIn("provider_unavailable", names)
        self.assertFalse(self.alerts.is_healthy())


if __name__ == "__main__":
    unittest.main()
