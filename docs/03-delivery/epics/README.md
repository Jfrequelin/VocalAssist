# 📋 Épics - Overview

**Last Updated**: 2026-04-30  
**Status**: 5 epics defined (127 story points total)

---

## 📊 Épics Summary

| Epic | Domain | Status | Estimation | Priority | Timeline |
|------|--------|--------|-----------|----------|----------|
| 🟦 [EDGE-firmware-esp32-s3.md](EDGE-firmware-esp32-s3.md) | Firmware edge | 🔴 Not started | 50-55 pt | 🔴 Critical | Week 1-2 |
| 🟩 [SRV-stc-tts-server.md](SRV-stc-tts-server.md) | Server central | 🟡 In progress | 37-40 pt | 🔴 Critical | Week 1-2 |
| 🟧 [ORCH-orchestrator-local-first.md](ORCH-orchestrator-local-first.md) | Orchestration | 🟡 In progress | 36-40 pt | 🟠 High | Week 1-2 |
| 🟣 [DOM-home-assistant.md](DOM-home-assistant.md) | Domotique | 🔴 Not started | 21-24 pt | 🟠 High | Week 2+ |
| 🔴 [OBS-observability.md](OBS-observability.md) | Cross-cutting | 🟡 In progress | 25-29 pt | 🟠 High | Week 1-2 |
| **TOTAL** | **-** | **-** | **169-188 pt** | **-** | **-** |

---

## 🎯 Sprint 2 Weeks Focus

### Week 1: Foundation (EDGE-01 to EDGE-04, SRV-01 to SRV-06, OBS-01 to OBS-05)

**Parallel tracks**:
- **EDGE**: Audio capture + codecs + wake word engine setup (EDGE-01 to EDGE-04)
- **SRV**: FastAPI server + STT + TTS pipelines (SRV-01 to SRV-06)
- **OBS**: Correlation ID + logging infrastructure (OBS-01 to OBS-05)
- **ORCH**: Intent parser baseline (ORCH-01, ORCH-05)

**Deliverables**:
- ✅ EDGE: Capture audio + codec working
- ✅ SRV: STT transcription + TTS synthesis baseline
- ✅ OBS: Correlation tracking + structured logs
- ✅ ORCH: Intent + provider schema defined

### Week 2: Integration + Validation (EDGE-05 to EDGE-10, ORCH-02 to ORCH-10, DOM-01 to DOM-08)

**Parallel tracks**:
- **EDGE**: HTTP client + TTS playback + robustness (EDGE-05 to EDGE-10)
- **ORCH**: Parameter extraction + clarification + testing (ORCH-02 to ORCH-10)
- **DOM**: HA integration + light/temperature/scenes (DOM-01 to DOM-08)
- **OBS**: Metrics + log tooling + dashboards (OBS-06 to OBS-11)

**Deliverables**:
- ✅ EDGE: End-to-end audio path working
- ✅ ORCH: Local-first routing + Leon fallback validated
- ✅ DOM: 3 HA services working (light, temperature, scenes)
- ✅ OBS: Full tracing + metrics visible
- ✅ **Overall**: MVP vocal assistant live demonstration

---

## 📦 Epic Dependencies

```
OBS (Observability)
  ├─→ EDGE (w/ correlation_id)
  ├─→ SRV (w/ logging + metrics)
  ├─→ ORCH (w/ tracing)
  └─→ DOM (w/ action logging)

SRV (STT/TTS + Orchestrator)
  ├─→ OBS (correlation tracking)
  └─→ supports: ORCH, DOM, EDGE

ORCH (Local-First Router)
  ├─→ SRV (STT/TTS endpoints)
  ├─→ OBS (correlation tracing)
  └─→ supports: DOM, EDGE

EDGE (Firmware)
  ├─→ SRV (HTTP client to server)
  ├─→ OBS (logging via UART)
  └─→ independent: can develop offline

DOM (Home Assistant)
  ├─→ SRV (via ORCH routing)
  ├─→ ORCH (intent mapping)
  └─→ OBS (action tracing)
```

---

## 🚀 Parallel Execution Plan

### Critical Path (determines timeline)

1. **Day 1-2**: EDGE audio capture + SRV STT/TTS baseline = Foundation
2. **Day 2-3**: SRV orchestrator + EDGE HTTP client = Integration
3. **Day 4-5**: ORCH routing + testing, DOM HA setup = Feature complete
4. **Day 5+**: Refinement + performance tuning + demo

### Non-critical Path (can be deferred)

- Grafana dashboards (P2, can demo Prometheus raw)
- Advanced NLP (ORCH-01 baseline sufficient)
- Additional providers (ORCH-05 can start with 2 providers)

---

## 📈 Story Point Velocity

**Estimated total**: ~175 story points  
**Sprint capacity (5 days)**: ~60-80 story points expected  
**Spillover to Week 3**: 50-80 story points (OK, P2 items)

| Week | Planned | Actual | Velocity |
|------|---------|--------|----------|
| Week 1 (EDGE+SRV+OBS partial) | 60-70 pt | TBD | - |
| Week 2 (ORCH+DOM+OBS complete) | 60-70 pt | TBD | - |
| **Total 2 weeks** | **120-140 pt** | **TBD** | **TBD** |

---

## 🔗 Roadmap Alignment

- **Phase 2 (Prototype vocal)**: EDGE + SRV + ORCH MVP ✅ (this sprint)
- **Phase 3 (Domotique)**: DOM + ORCH advanced ✅ (sprint week 2+)
- **Phase 4 (Commandes avancées)**: Slots + clarification ⏳ (week 3-4)
- **Phase 5 (Apprentissage/mémoire)**: ML personality ⏳ (week 5-6)
- **Phase 6 (Scaling + cloud)**: Multi-device, cloud backup ⏳ (week 7+)

See [../roadmap.md](../roadmap.md) for full roadmap.

---

## 📚 Navigation

- **Sprint plan**: [../sprint-2-weeks.md](../sprint-2-weeks.md)
- **Individual epics**:
  - 🟦 [EDGE Firmware](EDGE-firmware-esp32-s3.md)
  - 🟩 [SRV Server](SRV-stc-tts-server.md)
  - 🟧 [ORCH Orchestrator](ORCH-orchestrator-local-first.md)
  - 🟣 [DOM Home Assistant](DOM-home-assistant.md)
  - 🔴 [OBS Observability](OBS-observability.md)
- **Architecture**: [../../02-architecture/system-architecture.md](../../02-architecture/system-architecture.md)
- **Workflow**: [../../../../WORKFLOW.md](../../../../WORKFLOW.md)

---

## ⚡ Quick Start Deploy

```bash
# 1. Review epic summaries (this file + individual epic docs)
cat docs/03-delivery/epics/README.md

# 2. Create GitHub tickets from epics
# (To be automated: scripts/create-tickets-from-epics.py)
./scripts/create-tickets-from-epics.sh

# 3. Sync locally
./scripts/sync.sh

# 4. Start sprint (assign to devs + estimate)
cat .tickets-local/INDEX.md
```

---

## 📝 Notes

- Each epic is self-contained but interdependent (see dependency graph above)
- Parallel execution recommended: assign different devs to EDGE, SRV, ORCH, DOM
- OBS is horizontal: integrate as epics proceed
- Estimation includes testing + documentation (not just coding)
- Risk factors included in individual epic estimates

---

**Created**: 2026-04-30  
**Owner**: VocalAssist Team
