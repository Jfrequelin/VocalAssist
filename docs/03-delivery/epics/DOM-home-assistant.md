# 🟣 Epic DOM: Home Assistant Integration

**Statut**: 🔴 Not Started  
**Owner**: TBD  
**Timeline**: Semaines 2+ (Sprint 2w minimal)  
**Estimation**: 18 pt (2 jours)  
**Priority**: 🟠 Haute (core use case)

---

## 📋 Description

Intégrer Home Assistant pour exécuter actions domotiques:
- **3 actions critiques MVP**: Lumière on/off, température, scène simple
- **REST API**: Utiliser HA REST API pour endpoint `/api/services/...`
- **State queries**: Récupérer état lumière/température actuels
- **Error handling**: Graceful fallback si HA indisponible
- **Logging**: Tracer toutes les actions domotiques

**Justification**: Principal use case de l'assistant vocal, validate orchestrator + SRV, foundation pour expansion future.

---

## 🎯 Critères d'acceptation

- [ ] Intégration HA REST API fonctionnelle
- [ ] Lumière: on/off/brightness/color commands (10 tests each)
- [ ] Température: query state + set thermostat (5 tests)
- [ ] Scène: activer scène prédéfinie (3 tests)
- [ ] État queries: récupérer état current (lights, thermostat)
- [ ] Error handling: HA down → graceful message à user
- [ ] 0 crashes sur 100+ actions domotiques
- [ ] Actions exécutées <1.5s (P95) end-to-end

---

## 📦 Sous-tâches (Tickets)

### Phase 1: HA API Integration (Jour 1)

**DOM-01**: Setup HA REST client  
- [ ] HA token generation (Settings → Long-lived tokens)
- [ ] HTTP client library (requests + retry)
- [ ] Config: `HA_ENDPOINT`, `HA_TOKEN` env vars
- [ ] Health check: `GET /api/` → verify connectivity
- [ ] Timeout: 1s per request (HA should respond quickly)

**DOM-02**: Light control (on/off/brightness)  
- [ ] API: `POST /api/services/light/turn_on`
  ```json
  {"entity_id": "light.living_room", "brightness": 200}
  ```
- [ ] Implement: `turn_on_light(entity, brightness=255)`, `turn_off_light(entity)`
- [ ] Test: 10 on/off cycles, 10 brightness changes, error cases
- [ ] Verify state: GET light entity after each action

### Phase 2: Climate Control (Jour 1)

**DOM-03**: Temperature/thermostat  
- [ ] Query current temp: `GET /api/states/climate.living_room`
- [ ] Set target: `POST /api/services/climate/set_temperature`
  ```json
  {"entity_id": "climate.living_room", "temperature": 22}
  ```
- [ ] Support modes: heating, cooling, auto
- [ ] Test: 5 temperature sets + verification
- [ ] Constraints: respect min/max (15-30°C)

**DOM-04**: Scene activation  
- [ ] API: `POST /api/services/scene/turn_on`
  ```json
  {"entity_id": "scene.good_morning"}
  ```
- [ ] Predefined scenes: good_morning, movie, night
- [ ] Test: activate + verify (lights off, etc.)
- [ ] 3 scenes × 3 tests = 9 scenarios

### Phase 3: Orchestrator Integration (Jour 2)

**DOM-05**: Action executor mapping  
- [ ] Integrate with ORCH intents: `turn_on_light`, `set_temperature`, etc.
- [ ] Map intent params to HA API calls
- [ ] Handle missing entity_id → clarification flow
- [ ] Test: 20 orchestrator → HA actions end-to-end

**DOM-06**: Error handling + fallback  
- [ ] HA unreachable → user message ("Home Assistant pas disponible")
- [ ] Invalid entity → log + user feedback
- [ ] Rate limiting: max 10 reqs/min per entity
- [ ] Circuit breaker: if HA >3 failures, fallback 30s

### Phase 4: Testing (Jour 2)

**DOM-07**: Unit + integration tests  
- [ ] Mock HA API for unit tests
- [ ] Integration tests against real HA instance
- [ ] 10 light on/off cycles → 0 errors
- [ ] 5 temperature sets + verification
- [ ] 3 scene activations
- [ ] Error scenarios: timeout, invalid entity, auth fail

**DOM-08**: Performance + reliability  
- [ ] Measure latency per action type (median, P95, P99)
- [ ] Sustained load: 50 consecutive actions
- [ ] HA disconnect/reconnect recovery
- [ ] 24h stability test (automated actions every 5 min)

---

## 📊 Estimations (Story Points)

| Tâche | Estimée | Facteur risque | Réelle |
|-------|---------|---|--------|
| DOM-01 (HA API setup) | 2 pt | 0.8 | 1.6 pt |
| DOM-02 (Light control) | 4 pt | 1.0 | 4 pt |
| DOM-03 (Temperature) | 3 pt | 1.0 | 3 pt |
| DOM-04 (Scenes) | 2 pt | 0.8 | 1.6 pt |
| DOM-05 (ORCH integration) | 3 pt | 1.1 | 3-4 pt |
| DOM-06 (Error handling) | 2 pt | 0.9 | 1.8 pt |
| DOM-07 (Unit tests) | 3 pt | 0.9 | 2.7 pt |
| DOM-08 (Perf tests) | 3 pt | 1.2 | 3.6 pt |
| **Total** | **22 pt** | **-** | **21-24 pt** |

---

## 🔗 Dépendances

- ✅ **Home Assistant**: Instance running locally (Docker OK)
- ⏳ **ORCH-05**: Provider registry (for HA climate state provider)
- ✅ **SRV ready**: Orchestrator + routing working

## 🚨 Risques + Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| HA API changes (minor versions) | Requests fail | Version pinning, API compatibility layer |
| Entity naming inconsistency | Wrong execution | Centralized entity registry, validation |
| Network latency | >1.5s P95 | Connection pooling, caching, timeout tuning |
| User says "alexa turn on everything" | Unintended consequences | Max 1 entity per command, clarification |

---

## 📝 HA API Examples

### List all entities
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://homeassistant.local:8123/api/states
```

### Turn on light with brightness
```bash
curl -X POST \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"entity_id":"light.living_room","brightness":200}' \
     http://homeassistant.local:8123/api/services/light/turn_on
```

### Get climate entity state
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://homeassistant.local:8123/api/states/climate.living_room
```

### Activate scene
```bash
curl -X POST \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{"entity_id":"scene.good_morning"}' \
     http://homeassistant.local:8123/api/services/scene/turn_on
```

---

## 🎯 Supported Intents (MVP)

| Intent | Example | HA Service | Params |
|--------|---------|-----------|--------|
| `turn_on_light` | "Allume le salon" | `light/turn_on` | entity_id, brightness |
| `turn_off_light` | "Éteins la lumière" | `light/turn_off` | entity_id |
| `set_brightness` | "Augmente la lumière" | `light/turn_on` | entity_id, brightness |
| `set_temperature` | "Mets 22°C" | `climate/set_temperature` | entity_id, temperature |
| `activate_scene` | "Bon matin" | `scene/turn_on` | entity_id |
| `get_lights_state` | "Que lights sont allumées?" | `light/*` (query) | - |
| `get_temperature` | "Quelle est la température?" | `climate/*` (query) | - |

---

## ✅ Definition of Done

- [ ] HA REST client working (health check passes)
- [ ] Light control: on/off/brightness (10 tests each)
- [ ] Temperature: query + set (5 tests)
- [ ] Scenes: activate (3 tests)
- [ ] Error handling: graceful fallback
- [ ] 100+ actions zero crashes
- [ ] Latency P95 < 1.5s
- [ ] Integration tests passing
- [ ] Code review + approved
- [ ] Commit + pushed

---

**Créé**: 2026-04-30  
**Roadmap**: [docs/03-delivery/roadmap.md](../roadmap.md)  
**Sprint**: [docs/03-delivery/sprint-2-weeks.md](../sprint-2-weeks.md)
