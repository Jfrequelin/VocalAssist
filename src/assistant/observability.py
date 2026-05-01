"""Observabilité produit: KPI, tracing corrélé, alertes.

Module léger sans dépendance externe. Les métriques sont collectées
en mémoire et peuvent être exportées (JSON/texte Prometheus-like).

Usage:
    from src.assistant.observability import MetricsCollector, AlertManager

    collector = MetricsCollector()
    collector.record_interaction(correlation_id="...", ...)
    alerts = AlertManager(collector)
    alerts.check_all()
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import median
from typing import Sequence


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------


@dataclass
class InteractionTrace:
    """Trace complète d'une interaction de bout en bout."""

    correlation_id: str
    intent: str
    route: str  # "local" | "leon" | "clarification" | "error"
    stt_ms: float = 0.0
    orchestrator_ms: float = 0.0
    tts_ms: float = 0.0
    provider_name: str | None = None
    provider_ms: float = 0.0
    success: bool = True
    error_type: str | None = None  # "provider_failure" | "leon_failure" | "timeout" | ...
    timestamp: float = field(default_factory=time.time)

    @property
    def e2e_ms(self) -> float:
        return self.stt_ms + self.orchestrator_ms + self.tts_ms + self.provider_ms


@dataclass
class KpiSummary:
    """KPI agrégés sur un ensemble de traces."""

    total_interactions: int
    success_count: int
    failure_count: int
    success_rate: float  # 0.0–1.0
    median_e2e_ms: float
    p95_e2e_ms: float
    intent_distribution: dict[str, int]
    route_distribution: dict[str, int]
    error_distribution: dict[str, int]

    @property
    def leon_failure_count(self) -> int:
        return self.error_distribution.get("leon_failure", 0)

    @property
    def provider_failure_count(self) -> int:
        return self.error_distribution.get("provider_failure", 0)


# ---------------------------------------------------------------------------
# Collecteur de métriques
# ---------------------------------------------------------------------------


class MetricsCollector:
    """Collecte les traces d'interactions et calcule les KPI."""

    def __init__(self) -> None:
        self._traces: list[InteractionTrace] = []

    # -- Enregistrement -------------------------------------------------------

    def record(self, trace: InteractionTrace) -> None:
        """Enregistre une trace d'interaction complète."""
        self._traces.append(trace)

    def record_interaction(
        self,
        *,
        correlation_id: str,
        intent: str,
        route: str,
        stt_ms: float = 0.0,
        orchestrator_ms: float = 0.0,
        tts_ms: float = 0.0,
        provider_name: str | None = None,
        provider_ms: float = 0.0,
        success: bool = True,
        error_type: str | None = None,
    ) -> InteractionTrace:
        trace = InteractionTrace(
            correlation_id=correlation_id,
            intent=intent,
            route=route,
            stt_ms=stt_ms,
            orchestrator_ms=orchestrator_ms,
            tts_ms=tts_ms,
            provider_name=provider_name,
            provider_ms=provider_ms,
            success=success,
            error_type=error_type,
        )
        self.record(trace)
        return trace

    # -- Accès aux données brutes ---------------------------------------------

    def all_traces(self) -> list[InteractionTrace]:
        return list(self._traces)

    def traces_for_correlation(self, correlation_id: str) -> list[InteractionTrace]:
        return [t for t in self._traces if t.correlation_id == correlation_id]

    def unique_correlation_ids(self) -> set[str]:
        return {t.correlation_id for t in self._traces}

    def reset(self) -> None:
        """Vide toutes les traces (utile pour les tests)."""
        self._traces.clear()

    # -- KPI ------------------------------------------------------------------

    def kpi_summary(self, traces: Sequence[InteractionTrace] | None = None) -> KpiSummary:
        """Calcule les KPI agrégés sur les traces fournies (ou toutes)."""
        population = list(traces) if traces is not None else self._traces
        if not population:
            return KpiSummary(
                total_interactions=0,
                success_count=0,
                failure_count=0,
                success_rate=0.0,
                median_e2e_ms=0.0,
                p95_e2e_ms=0.0,
                intent_distribution={},
                route_distribution={},
                error_distribution={},
            )

        success_count = sum(1 for t in population if t.success)
        failure_count = len(population) - success_count

        e2e_values = sorted(t.e2e_ms for t in population)
        idx_95 = max(0, int((len(e2e_values) - 1) * 0.95))

        intent_dist: dict[str, int] = defaultdict(int)
        route_dist: dict[str, int] = defaultdict(int)
        error_dist: dict[str, int] = defaultdict(int)

        for t in population:
            intent_dist[t.intent] += 1
            route_dist[t.route] += 1
            if t.error_type:
                error_dist[t.error_type] += 1

        return KpiSummary(
            total_interactions=len(population),
            success_count=success_count,
            failure_count=failure_count,
            success_rate=success_count / len(population),
            median_e2e_ms=median(e2e_values),
            p95_e2e_ms=e2e_values[idx_95],
            intent_distribution=dict(intent_dist),
            route_distribution=dict(route_dist),
            error_distribution=dict(error_dist),
        )

    def kpi_for_parcours(self, intent: str) -> KpiSummary:
        """KPI filtrés sur un parcours (intent) donné."""
        traces = [t for t in self._traces if t.intent == intent]
        return self.kpi_summary(traces)

    # -- Export ---------------------------------------------------------------

    def export_prometheus_text(self) -> str:
        """Exporte les métriques dans un format texte Prometheus-compatible."""
        kpi = self.kpi_summary()
        lines: list[str] = [
            "# HELP interactions_total Total d'interactions enregistrees",
            "# TYPE interactions_total counter",
            f"interactions_total {kpi.total_interactions}",
            "# HELP interactions_success_total Interactions reussies",
            "# TYPE interactions_success_total counter",
            f"interactions_success_total {kpi.success_count}",
            "# HELP interactions_failure_total Interactions en echec",
            "# TYPE interactions_failure_total counter",
            f"interactions_failure_total {kpi.failure_count}",
            "# HELP success_rate Taux de succes (0-1)",
            "# TYPE success_rate gauge",
            f"success_rate {kpi.success_rate:.4f}",
            "# HELP e2e_latency_ms_median Latence E2E mediane (ms)",
            "# TYPE e2e_latency_ms_median gauge",
            f"e2e_latency_ms_median {kpi.median_e2e_ms:.2f}",
            "# HELP e2e_latency_ms_p95 Latence E2E p95 (ms)",
            "# TYPE e2e_latency_ms_p95 gauge",
            f"e2e_latency_ms_p95 {kpi.p95_e2e_ms:.2f}",
        ]
        for route, count in kpi.route_distribution.items():
            lines.append(f'routing_total{{route="{route}"}} {count}')
        for err, count in kpi.error_distribution.items():
            lines.append(f'errors_total{{type="{err}"}} {count}')
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Alertes
# ---------------------------------------------------------------------------


@dataclass
class Alert:
    level: str  # "warning" | "critical"
    name: str
    message: str
    value: float
    threshold: float


class AlertManager:
    """Vérifie les seuils critiques et lève des alertes."""

    def __init__(
        self,
        collector: MetricsCollector,
        *,
        max_failure_rate: float = 0.20,           # 20%
        max_p95_latency_ms: float = 2500.0,
        max_leon_failure_rate: float = 0.10,      # 10%
        max_provider_failure_rate: float = 0.10,  # 10%
        min_interactions_for_alert: int = 3,
    ) -> None:
        self._collector = collector
        self.max_failure_rate = max_failure_rate
        self.max_p95_latency_ms = max_p95_latency_ms
        self.max_leon_failure_rate = max_leon_failure_rate
        self.max_provider_failure_rate = max_provider_failure_rate
        self.min_interactions = min_interactions_for_alert

    def check_all(self) -> list[Alert]:
        """Retourne la liste de toutes les alertes actives."""
        alerts: list[Alert] = []
        kpi = self._collector.kpi_summary()

        if kpi.total_interactions < self.min_interactions:
            return alerts

        # Taux d'échec global
        failure_rate = 1.0 - kpi.success_rate
        if failure_rate > self.max_failure_rate:
            alerts.append(Alert(
                level="critical",
                name="high_failure_rate",
                message=f"Taux d'echec {failure_rate:.1%} > seuil {self.max_failure_rate:.1%}",
                value=failure_rate,
                threshold=self.max_failure_rate,
            ))

        # Latence P95
        if kpi.p95_e2e_ms > self.max_p95_latency_ms:
            alerts.append(Alert(
                level="warning",
                name="high_p95_latency",
                message=(
                    f"Latence P95 {kpi.p95_e2e_ms:.0f}ms "
                    f"> seuil {self.max_p95_latency_ms:.0f}ms"
                ),
                value=kpi.p95_e2e_ms,
                threshold=self.max_p95_latency_ms,
            ))

        # Pannes Leon
        if kpi.total_interactions > 0:
            leon_rate = kpi.leon_failure_count / kpi.total_interactions
            if leon_rate > self.max_leon_failure_rate:
                alerts.append(Alert(
                    level="critical",
                    name="leon_unavailable",
                    message=(
                        f"Taux panne Leon {leon_rate:.1%} "
                        f"> seuil {self.max_leon_failure_rate:.1%}"
                    ),
                    value=leon_rate,
                    threshold=self.max_leon_failure_rate,
                ))

            # Pannes provider
            provider_rate = kpi.provider_failure_count / kpi.total_interactions
            if provider_rate > self.max_provider_failure_rate:
                alerts.append(Alert(
                    level="critical",
                    name="provider_unavailable",
                    message=(
                        f"Taux panne provider {provider_rate:.1%} "
                        f"> seuil {self.max_provider_failure_rate:.1%}"
                    ),
                    value=provider_rate,
                    threshold=self.max_provider_failure_rate,
                ))

        return alerts

    def is_healthy(self) -> bool:
        return len(self.check_all()) == 0
