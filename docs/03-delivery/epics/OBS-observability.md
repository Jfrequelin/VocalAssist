# 🔴 Epic OBS: Observabilité & Monitoring

**Statut**: 🟡 In Progress (Partial)  
**Owner**: TBD  
**Timeline**: Semaines 1-2 (Sprint 2w, cross-cutting)  
**Estimation**: 15 pt (1.5 jours setup + integration)  
**Priority**: 🟠 Haute (horizontal, supporte debugging)

---

## 📋 Description

Mettre en place observabilité complète pour debugging global:
- **Correlation ID**: UUID unique par interaction (edge → server → leon)
- **Structured logging**: JSON logs (timestamp, level, service, msg)
- **Request tracing**: Tracer path complet (STT → intent → TTS → playback)
- **Metrics**: Prometheus counters/histograms (latency, errors, etc.)
- **Log aggregation**: Consul.log + rotation + archival
- **Dashboards**: Grafana pour visualiser trends (optional P2)

**Justification**: Debugging P1 (correlation tracing), performance monitoring, SLA tracking, production readiness.

---

## 🎯 Critères d'acceptation

- [ ] Correlation ID: généré edge, transmis à tous les services
- [ ] Logs JSON structurés: timestamp, level, correlation_id, service, message
- [ ] All services logging: EDGE firmware, SRV, ORCH
- [ ] Metrics endpoint: `/metrics` (Prometheus format)
- [ ] Log file: `/var/log/vocalassist/server.log` (rotating, 100MB per file)
- [ ] Request tracing: Full path loggé (start-time, steps, end-time, latency P50/P95)
- [ ] 0 missing correlation IDs on traced requests
- [ ] Metrics queryable + historical data available

---

## 📦 Sous-tâches (Tickets)

### Phase 1: Correlation ID Infrastructure (Jour 1)

**OBS-01**: UUID correlation ID schema  
- [ ] Define: UUID format, generation location (edge)
- [ ] Propagation: Edge → SRV (header `X-Correlation-ID`)
- [ ] Auth: Include in all logs, responses
- [ ] Validation: Ensure non-empty on all requests
- [ ] Test: 100 requests → 100 unique correlations

**OBS-02**: Structured logging setup  
- [ ] JSON format standard:
  ```json
  {
    "timestamp": "2026-04-30T14:32:10.123456Z",
    "level": "INFO|WARN|ERROR|DEBUG",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "service": "server|EDGE|leon-client",
    "component": "stc|tts|orchestrator",
    "message": "STT completed",
    "duration_ms": 1234,
    "error": null
  }
  ```
- [ ] Library: `python-json-logger` + custom formatters
- [ ] Test: Produce 10 different message types

### Phase 2: Logging Integration per Service (Jour 1)

**OBS-03**: Server-side logging  
- [ ] FastAPI middleware: log request/response + correlation_id
- [ ] Service logs: STT start/end + latency, TTS start/end + latency
- [ ] Error logs: exceptions + stack trace + recovery action
- [ ] File rotation: `/var/log/vocalassist/server.log` (100 MB/file, 10 files max)
- [ ] Test: 500 requests logged → verify file rotation

**OBS-04**: Edge firmware logging  
- [ ] Serial/UART logging: correlation_id per interaction
- [ ] Log buffer: Store locally, sync to server on connection
- [ ] Levels: ERROR, WARN, INFO (DEBUG optional, high CPU)
- [ ] Test: 100 interactions → extract correlation trace

**OBS-05**: Orchestrator + Leon client tracing  
- [ ] Log parsing → intent recognition
- [ ] Log routing decision (local vs Leon)
- [ ] Log Leon request + response time
- [ ] Log error handling + fallback
- [ ] Test: 50 orchestrator traces complete

### Phase 3: Metrics + Monitoring (Jour 2)

**OBS-06**: Prometheus metrics  
- [ ] Counters:
  - `stt_requests_total` (labels: status=success|error)
  - `tts_requests_total` (labels: status=success|error)
  - `orchestrator_routing_total` (labels: route=local|leon|error)
  - `domotique_actions_total` (labels: action=light|thermostat|scene, status=ok|fail)
- [ ] Histograms (buckets: 100, 200, 500, 1000, 2000, 5000 ms):
  - `stt_latency_seconds` (duration of transcription)
  - `tts_latency_seconds` (duration of synthesis)
  - `orchestrator_latency_seconds` (total routing time)
  - `leon_latency_seconds` (Leon API response time)
  - `domotique_latency_seconds` (HA API response time)
- [ ] Gauges:
  - `orchestrator_queue_size` (requests pending)
  - `leon_availability` (0=down, 1=up)
  - `ha_availability` (0=down, 1=up)
  - `memory_usage_bytes` (current memory consumption)
- [ ] Endpoint: `GET /metrics` (text format, Prometheus compatible)

**OBS-07**: Metrics integration per service  
- [ ] SRV: Export STT+TTS+orchestrator metrics
- [ ] ORCH: Export routing + provider latencies
- [ ] DOM: Export HA action counts + latencies
- [ ] Scrape interval: 15s (Prometheus config)
- [ ] Test: 100 requests → verify histogram buckets

### Phase 4: Log Aggregation + Queries (Jour 2)

**OBS-08**: Log file management  
- [ ] Directory: `/var/log/vocalassist/`
- [ ] Files: `server.log`, `server.log.1`, `server.log.2`, ...
- [ ] Retention: 10 GB max (automatic cleanup old files)
- [ ] Compression: Optional gzip older files
- [ ] Test: Rotate 1000 requests → verify cleanup

**OBS-09**: Query tooling (helper scripts)  
- [ ] `./scripts/tail-logs.sh` — tail latest entries
- [ ] `./scripts/find-correlation.sh <correlation_id>` — extract full trace
- [ ] `./scripts/latency-stats.sh <service>` — histogram of latencies
- [ ] Tests: Verify scripts on sample logs

### Phase 5: Validation + Dashboard (Jour 2)

**OBS-10**: End-to-end tracing validation  
- [ ] Execute 50 full interactions: EDGE → SRV → ORCH → (optional DOM) → TTS → response
- [ ] For each: extract correlation_id from logs
- [ ] Verify: All steps present, latencies reasonable
- [ ] Generate trace visualization: timeline per interaction
- [ ] Target: 99% of requests have complete trace

**OBS-11**: Metrics visualization (optional, P2)  
- [ ] Docker Compose: Prometheus + Grafana local
- [ ] Dashboard: Latency trends, error rates, availability
- [ ] Alerts: Latency P95 > 2.5s, error rate > 5%
- [ ] Documentation: How to access dashboard

---

## 📊 Estimations (Story Points)

| Tâche | Estimée | Facteur risque | Réelle |
|-------|---------|---|--------|
| OBS-01 (Correlation ID) | 2 pt | 0.8 | 1.6 pt |
| OBS-02 (Logging setup) | 2 pt | 0.9 | 1.8 pt |
| OBS-03 (Server logging) | 3 pt | 1.0 | 3 pt |
| OBS-04 (Edge logging) | 2 pt | 1.2 | 2.4 pt |
| OBS-05 (Orch tracing) | 2 pt | 0.9 | 1.8 pt |
| OBS-06 (Prometheus metrics) | 3 pt | 1.0 | 3 pt |
| OBS-07 (Metrics integration) | 2 pt | 1.1 | 2.2 pt |
| OBS-08 (Log management) | 2 pt | 0.8 | 1.6 pt |
| OBS-09 (Query tools) | 2 pt | 0.9 | 1.8 pt |
| OBS-10 (Trace validation) | 2 pt | 1.0 | 2 pt |
| OBS-11 (Grafana dashboard) | 3 pt | 1.2 (monitoring setup) | 3.6 pt |
| **Total** | **25 pt** | **-** | **25-29 pt** |

---

## 🔗 Dépendances

- ✅ **Python libs**: python-json-logger, prometheus-client
- ✅ **Optional**: Prometheus server, Grafana (Docker)
- ⏳ **Cross-cutting**: All epics (EDGE, SRV, ORCH, DOM) must integrate

## 🚨 Risques + Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| Logging overhead (CPU/disk) | Latency +5-10% | Async logging, log level config, sampling |
| Disk fills up | Server down | Log rotation + cleanup automated |
| Correlation ID not propagated | Traces broken | Middleware validation, tests per layer |
| Metrics cardinality explosion | Memory issues | Limit label values, use consistent names |

---

## 📝 Logging Architecture

```
┌─────────────────────────────────────────┐
│         Application Code                 │
├─────────────────────────────────────────┤
│  Log: logging.info("msg", extra={...})   │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│      JSON Logger Formatter               │
│  (add correlation_id, timestamp, etc.)   │
└──────────────────┬──────────────────────┘
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
    ┌─────────┐          ┌─────────┐
    │ STDOUT  │          │  FILE   │
    │ (console)│         │ (server.log)
    └─────────┘          └─────────┘
                              │
                              ▼
                      ┌────────────────┐
                      │ Log Rotation   │
                      │ (100MB max)    │
                      └────────────────┘
```

## 📝 Query Examples

### Extract correlation trace
```bash
./scripts/find-correlation.sh 550e8400-e29b-41d4-a716-446655440000
# Output:
# 14:32:10.001 [EDGE] Audio capture started
# 14:32:10.150 [SRV] STT processing
# 14:32:11.234 [SRV] Intent: turn_on_light
# 14:32:11.235 [ORCH] Route: local
# 14:32:11.236 [HA] Light.living_room turned on
# 14:32:11.250 [SRV] TTS generating
# 14:32:11.800 [SRV] Response sent (799 ms total)
```

### Latency stats
```bash
./scripts/latency-stats.sh stt
# Output:
# STT Latency (500 samples):
# P50: 980 ms
# P95: 1350 ms
# P99: 1500 ms
```

---

## ✅ Definition of Done

- [ ] Correlation ID: generated + propagated to all services
- [ ] Logging: JSON structured in all services
- [ ] Logs rotating: `/var/log/vocalassist/server.log`
- [ ] Metrics: Prometheus endpoint working
- [ ] 50 end-to-end traces: complete + correct
- [ ] Query scripts: working + tested
- [ ] No correlation ID gaps in traces
- [ ] Code review + approved
- [ ] Commit + pushed

---

**Créé**: 2026-04-30  
**Roadmap**: [docs/03-delivery/roadmap.md](../roadmap.md)  
**Sprint**: [docs/03-delivery/sprint-2-weeks.md](../sprint-2-weeks.md)
