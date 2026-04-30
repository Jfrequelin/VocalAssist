# 🟧 Epic ORCH: Orchestrateur Local-First

**Statut**: 🟡 In Progress (Prototype done)  
**Owner**: TBD  
**Timeline**: Semaines 1-2 (Sprint 2w)  
**Estimation**: 20 pt (2 jours refinement + tests)  
**Priority**: 🟠 Haute (bloque intents avancés)

---

## 📋 Description

Renforcer l'orchestrateur pour supporter commandes paramétrées + décision routing avancé:
- **Intent parsing**: Extraire intent + parameters (slots)
- **Parameter validation**: Vérifier contraintes (ex: temperature 15-30°C)
- **Clarification**: Demander paramètres manquants ("Quelle pièce?")
- **Provider resolution**: Mapper sources données (météo API, radio flux, etc.)
- **Fallback logic**: Local → Leon → Error handling robuste
- **Auditing**: Tracer toutes les décisions pour debug

**Justification**: Supporter cas d'usage réalistes (commandes paramétrées), robustesse fallback, debugging tracing.

---

## 🎯 Critères d'acceptation

- [ ] Intent + NER extraction: 95% accuracy sur 200 utterances de test
- [ ] Parameter validation: 100% coverage (type, range, enum)
- [ ] Clarification flow: Propose max 2 options (timeout 3s)
- [ ] Provider resolution: 5 providers testés (météo, musique, etc.)
- [ ] Fallback chain: Local → Leon → Graceful error
- [ ] All decisions logged avec correlation_id + latency
- [ ] 0 crashes sur 300+ interactions (mixed intent/param scenarios)

---

## 📦 Sous-tâches (Tickets)

### Phase 1: Intent + Parameter Extraction (Jour 1)

**ORCH-01**: Intent parser + NER  
- [ ] Utiliser spaCy + French model (`fr_core_news_sm`)
- [ ] Extract entities: LOCATION, TEMPERATURE, PERSON, etc.
- [ ] Test: 100 utterances avec annotations gold standard
- [ ] Seuil de confiance: ≥ 0.8 pour accepter

**ORCH-02**: Parameter slots schema  
- [ ] Define slots par intent (ex: `set_temperature`: room, temperature, mode)
- [ ] Type validation: string, int (range), enum, timestamp
- [ ] Slots JSON structure:
```json
{
  "intent": "set_temperature",
  "slots": {
    "room": {"value": "living room", "type": "string", "required": true},
    "temperature": {"value": 22, "type": "int", "min": 15, "max": 30},
    "mode": {"value": "heating", "type": "enum", "options": ["heating", "cooling"]}
  }
}
```

### Phase 2: Validation + Clarification (Jour 1-2)

**ORCH-03**: Slot validation + defaults  
- [ ] Check each slot against constraints
- [ ] Apply defaults si missing non-critical
- [ ] Return validation errors avec user-friendly messages
- [ ] Test: 50 scenarios (valid + invalid)

**ORCH-04**: Clarification dialog  
- [ ] Detect missing critical slots (required=true)
- [ ] Generate clarification question ("Quelle pièce: salon ou chambre?")
- [ ] Support max 2 options (keep UX simple)
- [ ] Timeout 3s → default ou error
- [ ] Test: 20 clarification flows end-to-end

### Phase 3: Provider Resolution (Jour 2)

**ORCH-05**: Provider registry  
- [ ] Abstract provider interface: `fetch_data(query) → data`
- [ ] Implement 5 providers (MVP):
  - Weather API (OpenWeatherMap)
  - Music provider (Spotify API ou local)
  - Radio stream provider (TuneIn API)
  - Home temp provider (Home Assistant)
  - Time provider (local)

**ORCH-06**: Provider fallback + caching  
- [ ] Try primary provider, fallback à secondary
- [ ] Cache results 5 min (météo, statut lights)
- [ ] Error handling: graceful degradation
- [ ] Logging: provider latency + errors

### Phase 4: Orchestrator Core Logic Refinement (Jour 2)

**ORCH-07**: Decision flow refactoring  
- [ ] Clarify routing chain: local → parameterized → Leon → error
- [ ] Add state machine: (idle) → (parsing) → (validating) → (executing) → (responding)
- [ ] Support async operations (API calls)
- [ ] Timeout management (per-stage)

**ORCH-08**: Correlation tracing  
- [ ] Generate unique correlation_id per request UUID
- [ ] Pass throughout entire flow (logs, API calls, responses)
- [ ] Enable complete request tracing for debugging
- [ ] Test: extract full trace from logs for 10 requests

### Phase 5: Testing + Validation (Jour 3)

**ORCH-09**: Intent + parameter test suite  
- [ ] Unit tests: 200+ parametrized utterances
- [ ] Coverage: intent accuracy, NER extraction, slot validation
- [ ] Edge cases: typos, abbreviations, multi-language mixing
- [ ] Target: 95% accuracy on intent + 90% on slots

**ORCH-10**: End-to-end orchestrator tests  
- [ ] Scenario 1: Local command (stop/mute) → immediate response
- [ ] Scenario 2: Parameterized (set temp) → validation + execution
- [ ] Scenario 3: Missing slot (clarification) → user interaction
- [ ] Scenario 4: Unknown intent (Leon fallback) → service response
- [ ] Scenario 5: Provider fail → graceful error
- [ ] Scenario 6: All scenarios 50x → 0 crashes

---

## 📊 Estimations (Story Points)

| Tâche | Estimée | Facteur risque | Réelle |
|-------|---------|---|--------|
| ORCH-01 (Intent+NER) | 5 pt | 1.1 (NLP tuning) | 5-6 pt |
| ORCH-02 (Slot schema) | 3 pt | 0.9 | 2-3 pt |
| ORCH-03 (Validation) | 3 pt | 0.8 | 2-3 pt |
| ORCH-04 (Clarification) | 4 pt | 1.2 (dialog flow) | 5 pt |
| ORCH-05 (Providers) | 5 pt | 1.3 (API integration) | 6-8 pt |
| ORCH-06 (Fallback/cache) | 3 pt | 1.0 | 3 pt |
| ORCH-07 (Routing refactor) | 4 pt | 0.9 | 3-4 pt |
| ORCH-08 (Tracing) | 2 pt | 0.8 | 1.6 pt |
| ORCH-09 (Intent tests) | 4 pt | 1.0 | 4 pt |
| ORCH-10 (E2E tests) | 4 pt | 1.1 | 4-5 pt |
| **Total** | **37 pt** | **-** | **36-40 pt** |

---

## 🔗 Dépendances

- ✅ **Python libs**: spaCy, requests, cachetools
- ⏳ **SRV ready**: STT/TTS endpoints + Leon client working
- ⏳ **DOM-01**: Home Assistant integration (for provider)
- ✅ **OBS-01**: Correlation ID schema

## 🚨 Risques + Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| NER accuracy faible (<90%) | Wrong slot extraction | Ensemble models, custom training data |
| Clarification ambiguity | UX confusion | Simple 2-option max, clear phrasing |
| Provider timeouts | Latency > 2.5s | Provider-level timeout 1.5s, parallel calls |
| Slot validation trop strict | Legitimate requests rejected | Configurable thresholds, warning logs |

---

## 📝 Orchestrator State Machine

```
┌─────────────┐
│    IDLE     │
└──────┬──────┘
       │ Audio input
       ▼
┌──────────────────────┐
│     STT → TEXT       │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  INTENT PARSING      │
│  (spaCy + NER)       │
└──────┬───────────────┘
       │
       ├─→ [Local command?] ─→ Execute immediately ──┐
       │                                             │
       ├─→ [Parametrized?]                          │
       │    ├─→ Slots complete? ─→ Execute           │
       │    ├─→ Missing slots → Clarify (3s) ─→     │
       │                                             │
       └─→ [Unknown intent?] ─→ Leon fallback ──→   │
                                                    │
       ◄──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│  TTS → AUDIO         │
│  (streaming)         │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│   RESPOND TO EDGE    │
└──────┬───────────────┘
       │
       ▼
┌─────────────┐
│    IDLE     │
└─────────────┘
```

---

## ✅ Definition of Done

- [ ] Intent parsing 95% accuracy on test set
- [ ] NER extraction 90% accuracy
- [ ] Parameter validation 100% coverage
- [ ] Clarification flow supports max 2 options
- [ ] 5 providers working + tested
- [ ] Correlation ID tracing complete
- [ ] Unit tests + integration tests passing
- [ ] Load test: 100 concurrent requests OK
- [ ] Code review + approved
- [ ] Commit + pushed

---

**Créé**: 2026-04-30  
**Roadmap**: [docs/03-delivery/roadmap.md](../roadmap.md)  
**Sprint**: [docs/03-delivery/sprint-2-weeks.md](../sprint-2-weeks.md)
