# 🟩 Epic SRV: STT/TTS Server + Orchestrateur

**Statut**: 🟡 In Progress (Core)  
**Owner**: TBD  
**Timeline**: Semaines 1-2 (Sprint 2w)  
**Estimation**: 35 pt (3 jours + tuning)  
**Priority**: 🔴 Critique (bloque ORCH + tests)

---

## 📋 Description

Server central Python pour orchestrer l'assistant vocal:
- **STT** (faster-whisper): Convertir audio PCM → texte français (WER ≤ 8%)
- **TTS** (Piper): Convertir texte → audio WAV local (latency <1s)
- **Orchestrateur**: Router requêtes (local commands → Leon fallback)
- **Streaming**: Retourner audio TTS chunked aux clients
- **Observabilité**: Logs structurés (correlation_id) + métriques Prometheus

**Justification**: Centraliser la logique métier, offrir STT/TTS performant, architecture modulaire.

---

## 🎯 Critères d'acceptation

- [ ] STT faster-whisper + French model ≤ 1.5s (P99) pour audio 5s
- [ ] WER (Word Error Rate) ≤ 8% sur corpus de test FR
- [ ] TTS Piper texte → audio ≤ 800 ms (P99) pour 20 words
- [ ] Streaming TTS en chunked avec jitter buffer <100 ms
- [ ] Orchestrateur route local-first (stop/mute/volume/brightness)
- [ ] Fallback Leon pour requêtes unknown (timeout 2s max)
- [ ] API contracts documentés (OpenAPI/Swagger)
- [ ] Logs JSON structurés avec correlation_id
- [ ] 0 crash sur 500+ interactions

---

## 📦 Sous-tâches (Tickets)

### Phase 1: Setup Server + STT (Jour 1)

**SRV-01**: Setup FastAPI server + STT pipeline  
- [ ] FastAPI app avec `/api/v1/audio` endpoint
- [ ] Télécharger modèle Whisper large-v2 (FR)
- [ ] faster-whisper init (GPU/CPU auto-detect)
- [ ] Timeout 2s pour audio 5s (WAV/opus support)

**SRV-02**: STT accuracy tuning  
- [ ] Test sur 100 samples de corpus FR
- [ ] Measure WER (Word Error Rate) baseline
- [ ] Ajust: language hint, prompt, beam size
- [ ] Target: WER < 8%

### Phase 2: TTS Setup (Jour 1-2)

**SRV-03**: Piper TTS integration  
- [ ] Télécharger Piper modèle FR (female preferred)
- [ ] Setup inference pipeline (numpy/onnx)
- [ ] Endpoint `/api/v1/tts` (text → audio/wav)
- [ ] Test latency P50/P95 pour 1→100 words

**SRV-04**: TTS streaming + chunking  
- [ ] Implement streaming response (audio/wav chunks, 2KB per chunk)
- [ ] Chunk interval: 20 ms audio @ 16 kHz = 320 bytes
- [ ] Client buffer control (jitter <100 ms)
- [ ] HTTP headers: `Content-Type: audio/wav`, `Transfer-Encoding: chunked`

### Phase 3: Orchestrateur (Jour 2)

**SRV-05**: Local-first router  
- [ ] Implémente `OrchestratorReply` (intent + answer + source)
- [ ] Route locale: stop, mute, volume, brightness (100% local)
- [ ] Timeout local: 100 ms max
- [ ] Logging source (local vs leon)

**SRV-06**: Leon fallback integr  
- [ ] Leon HTTP client avec `from assistant.leon_client import LeonClient`
- [ ] Endpoint config: env var `LEON_ENDPOINT`
- [ ] Timeout 2s, retry 1x on timeout
- [ ] Logging pour tracing service calls

### Phase 4: API + Observability (Jour 2-3)

**SRV-07**: API contracts + OpenAPI  
- [ ] POST `/api/v1/audio` (audio + correlation_id → text + intent)
- [ ] GET `/api/v1/tts` (text → audio stream)
- [ ] GET `/health` (status + uptime + queue size)
- [ ] Swagger UI auto-generated: `GET /docs`

**SRV-08**: Structured logging + correlation  
- [ ] JSON logs (timestamp, level, service, correlation_id, message)
- [ ] Log file `/var/log/vocalassist/server.log` (rotating)
- [ ] Request/response logging (input, latency, source)
- [ ] Error tracking (stack trace on exception)

**SRV-09**: Metrics + Prometheus  
- [ ] Counter: `stt_requests_total`, `tts_requests_total`
- [ ] Histogram: `stt_latency_seconds`, `tts_latency_seconds`
- [ ] Gauge: `orchestrator_queue_size`, `leon_availability`
- [ ] Endpoint: `GET /metrics` (Prometheus format)

### Phase 5: Testing (Jour 3-4)

**SRV-10**: Unit + integration tests  
- [ ] Test STT encoder (noise, accent, speed variations)
- [ ] Test TTS quality (phonemes, prosody check)
- [ ] Test orchestrateur routing (local vs leon)
- [ ] Test streaming response (chunk order, jitter)

**SRV-11**: Performance testing  
- [ ] Load test: 10 concurrent requests
- [ ] Measure latency P50/P95/P99
- [ ] CPU/Memory profiling (peak usage)
- [ ] Ensure no memory leaks (24h run)

---

## 📊 Estimations (Story Points)

| Tâche | Estimée | Facteur risque | Réelle |
|-------|---------|---|--------|
| SRV-01 (FastAPI setup) | 3 pt | 0.8 | 2-3 pt |
| SRV-02 (STT tuning) | 5 pt | 1.3 (data/tuning) | 6-8 pt |
| SRV-03 (Piper setup) | 3 pt | 0.9 | 3 pt |
| SRV-04 (Streaming) | 4 pt | 1.2 (buffering) | 5-6 pt |
| SRV-05 (Local router) | 3 pt | 0.8 | 2-3 pt |
| SRV-06 (Leon fallback) | 2 pt | 0.9 | 2 pt |
| SRV-07 (OpenAPI) | 2 pt | 0.7 | 1-2 pt |
| SRV-08 (Logging) | 3 pt | 0.8 | 2.4 pt |
| SRV-09 (Metrics) | 2 pt | 0.8 | 1.6 pt |
| SRV-10 (Unit tests) | 4 pt | 1.0 | 4 pt |
| SRV-11 (Perf tests) | 4 pt | 1.2 | 5 pt |
| **Total** | **35 pt** | **-** | **37-40 pt** |

---

## 🔗 Dépendances

- ✅ **Python 3.9+** mit FastAPI, faster-whisper, piper-tts, requests
- ⏳ **EDGE ready**: USB/network interface pour streaming audio
- ⏳ **OBS-01**: Correlation ID schema pour tracing
- ✅ **Leon instance**: Accessible au endpoint LEON_ENDPOINT

## 🚨 Risques + Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| STT latency > 1.5s | Timeout client | GPU support, model optimization |
| TTS quality dégradée | UX break | Pre-record common phrases, voice tuning |
| Server memory leak | Crash après 24h | Profiling avec memory_profiler, tests 48h |
| Leon unavailable | Requests drop | Fallback local responses, circuit breaker |
| Network congestion (streaming) | Jitter audio | Adaptive bitrate, buffer pre-allocation |

---

## 📝 Architecture

```
┌─────────────────────────────────────────────────┐
│           FastAPI Server (Port 8000)             │
├─────────────────────────────────────────────────┤
│                                                  │
│  POST /api/v1/audio                              │
│  ├─→ STT Pipeline (faster-whisper)               │
│  ├─→ Orchestrator (local-first router)           │
│  │   ├─→ Local response (stop/mute/volume)       │
│  │   └─→ Leon fallback (unknown intents)         │
│  ├─→ TTS Pipeline (Piper)                        │
│  └─→ Streaming response (chunked audio/wav)      │
│                                                  │
│  GET /health                                     │
│  └─→ Service status + metrics                    │
│                                                  │
│  GET /docs                                       │
│  └─→ OpenAPI Swagger UI                          │
│                                                  │
└─────────────────────────────────────────────────┘
```

### STT Pipeline Pseudo-code
```python
async def transcribe(audio_bytes: bytes, lang: str = "fr") -> str:
    # Load model (cached)
    model = whisper.load_model("large-v2")
    
    # Decode audio
    audio = whisper.load_audio(audio_bytes)
    
    # Transcribe (with hints for speed/accuracy)
    result = model.transcribe(
        audio,
        language=lang,
        temperature=0.0,  # deterministic
        prompt="Commandes vocales domicile.",  # hint
    )
    
    return result["text"]
```

---

## ✅ Definition of Done

- [ ] Server compilé + tests réussis
- [ ] STT WER ≤ 8% sur corpus de test
- [ ] TTS latency P95 < 1s
- [ ] Streaming response working + chunked
- [ ] Logs JSON structurés + correlation_id
- [ ] OpenAPI/Swagger doc accessible
- [ ] Load test: 10 concurrent requests OK
- [ ] Code review + approved
- [ ] Commit + pushed

---

**Créé**: 2026-04-30  
**Roadmap**: [docs/03-delivery/roadmap.md](../roadmap.md)  
**Sprint**: [docs/03-delivery/sprint-2-weeks.md](../sprint-2-weeks.md)
