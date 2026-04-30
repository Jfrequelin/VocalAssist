# 🟦 Epic EDGE: Firmware ESP32-S3

**Statut**: 🔴 Not Started  
**Owner**: TBD  
**Timeline**: Semaines 1-2 (Sprint 2w)  
**Estimation**: 40 pt (3-4 jours)  
**Priority**: 🔴 Critique (bloque SRV + ORCH)

---

## 📋 Description

Implémenter le firmware complet pour le satellite edge ESP32-S3:
- Capture audio micro 16 kHz PCM en continu
- Wake word detection local (précision ≥ 95%)
- Voice Activity Detection (VAD)
- Client HTTP vers serveur central
- Lecture flux audio TTS retourné du serveur
- Gestion état appareil (LED, bouton mute)
- Reconnexion automatique + exponential backoff

**Justification**: Réduire latence/charge serveur, gestion critique local, robustesse sans serveur.

---

## 🎯 Critères d'acceptation

- [ ] Capture audio 16 kHz PCM stéréo → mono en temps réel
- [ ] Wake word detection avec seuil config (97% acc min)
- [ ] VAD fonctionne, réduit false positives (-85%)
- [ ] Envoi audio compressé (opus/mulaw) au serveur avec correlation_id
- [ ] Reçoit réponse TTS (audio/wav) en <2.5s (P95)
- [ ] Joue audio TTS via haut-parleur sans artifacts
- [ ] Bouton mute physique + LED state indicator
- [ ] Reconnexion auto + logs (fichier SD ou UART)
- [ ] 0 crash sur 1000+ interactions de test

---

## 📦 Sous-tâches (Tickets)

### Phase 1: Capture Audio (Jour 1)

**EDGE-01**: Setup I2S mic + buffer circulaire  
- [ ] Config I2S mode master, clock 16 MHz
- [ ] Buffer 32 KB (2 sec @ 16 kHz PCM)
- [ ] Test avec white noise + voix réelle

**EDGE-02**: Compression audio  
- [ ] Codec Opus ou μ-law (test perf CPU)
- [ ] Frame 20 ms, payload ≤ 2 KB/frame
- [ ] Bitrate dynamique (8-32 kbps)

### Phase 2: Wake Word Local (Jour 2)

**EDGE-03**: Intégration wake word engine  
- [ ] Choose: SmallWakeWord, pmdl_88, PocketSphinx
- [ ] Train/tune sur "Nova" + variations
- [ ] Test batch 100x "Nova" → détection ≥ 99%
- [ ] Latence <200 ms (P50)

**EDGE-04**: VAD integration  
- [ ] WebRTC VAD ou syllable-based VAD
- [ ] Config sensibilité (3 levels: sensitive/normal/loose)
- [ ] Test: 0 false positives en 30 sec room noise

### Phase 3: Client HTTP (Jour 2)

**EDGE-05**: HTTP client + correlation tracking  
- [ ] HTTPs TLS 1.2 min
- [ ] Send audio chunks + correlation_id
- [ ] Retry logic: 3 tentatives max + backoff (1s, 2s, 4s)
- [ ] Timeout strict 2.5s par requête
- [ ] Payload: `{correlation_id, audio_b64, compression, samplerate}`

**EDGE-06**: TTS playback  
- [ ] Reçoit audio/wav stream en chunks
- [ ] Buffer + jitter control
- [ ] Play via I2S speaker output (16 kHz, 16-bit, mono)
- [ ] Zero-latency playback <100 ms après réception 1er chunk

### Phase 4: State Management + Robustness (Jour 3)

**EDGE-07**: Button + LED control  
- [ ] GPIO mute button → mute audio in + stop STT
- [ ] LED: RED (error), BLUE (listening), GREEN (ok), YELLOW (thinking)
- [ ] UART logging ou SD card logs

**EDGE-08**: Reconnection + crash recovery  
- [ ] Detect serveur unavailable → mode dégradé local (stop/mute/volume)
- [ ] Auto-reconnect avec exponential backoff (1s → 30s max)
- [ ] Watchdog timer 60s → reboot si hang
- [ ] Memory leak tests (24h continuous)

### Phase 5: Testing + Validation (Jour 4)

**EDGE-09**: Component testing  
- [ ] Unit tests audio pipeline (100 samples)
- [ ] Wake word accuracy test (1000x iterations)
- [ ] VAD false positive rate <1% (room noise 1h)
- [ ] HTTP retry logic (simulate server down)

**EDGE-10**: Integration testing  
- [ ] End-to-end: "Nova" → audio → serveur → TTS → playback
- [ ] 50x repeated calls → 0 crashes
- [ ] Measure: latency P50/P95/P99, jitter, CPU%, memory%

---

## 📊 Estimations (Story Points)

| Tâche | Estimée | Facteur risque | Réelle |
|-------|---------|---|--------|
| EDGE-01 (I2S mic) | 5 pt | 0.9 (known platform) | 4-5 pt |
| EDGE-02 (Codec) | 3 pt | 1.3 (perf tuning) | 4-5 pt |
| EDGE-03 (Wake word) | 8 pt | 1.5 (training/tuning) | 12-15 pt |
| EDGE-04 (VAD) | 5 pt | 1.2 | 6-8 pt |
| EDGE-05 (HTTP client) | 5 pt | 0.8 | 4 pt |
| EDGE-06 (TTS playback) | 4 pt | 1.0 | 4 pt |
| EDGE-07 (State mgmt) | 3 pt | 0.8 | 2-3 pt |
| EDGE-08 (Robustness) | 5 pt | 1.3 (edge cases) | 6-8 pt |
| EDGE-09 (Component tests) | 5 pt | 1.0 | 5 pt |
| EDGE-10 (Integration tests) | 4 pt | 1.2 | 5 pt |
| **Total** | **47 pt** | **-** | **50-55 pt** |

---

## 🔗 Dépendances

- ✅ **Hardware**: ESP32-S3 board, microphone, speaker, USB-C cable
- ✅ **Firmware base**: ESP-IDF 5.x, Arduino SDK compatible
- ⏳ **SRV ready**: STT/TTS endpoints disponibles (bloque tests full)
- ⏳ **OBS-01**: Correlation ID tracking schema (bloque tracing)

## 🚨 Risques + Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| Audio quality dégradée (noise, echo) | Accuracy -10% | AEC/NS firmware filters + client audio tests tôt |
| Wake word FN (non-détection) | UX break | Ensemble de modèles (multi-model voting) |
| Memory exhaustion après 24h | Crash | Profiling + heap tests chaque jour |
| Latence TTS >2.5s | Timeout client | Buffer pre-allocation + profiling réseau |
| Wifi disconnect fréquent | Mode dégradé | Stronger antenna + fallback local commands |

---

## 📝 Notes d'implémentation

### Audio Capture
```cpp
// Configuration I2S: 16 kHz, PCM, mono
i2s_config_t i2s_config = {
    .mode = I2S_MODE_MASTER | I2S_MODE_RX,
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 2,
    .dma_buf_len = 1024,
};
```

### Wake Word Library Candidates
- **PocketSphinx**: Lightweight (1 MB), offline, ok accuracy
- **SmallWakeWord**: Ultralightweight, Android trained
- **Edge Impulse**: Custom trained, good UX
- **TinyML WaveNet**: Experimental, promising

### Client HTTP Header
```http
POST /api/v1/audio HTTP/1.1
Content-Type: audio/opus
X-Correlation-ID: <uuid>
X-Sample-Rate: 16000
X-Compression: opus
Content-Length: 1024
```

---

## ✅ Definition of Done

- [ ] Code compilé, 0 warnings (-Wall -Wextra)
- [ ] Unit tests: ≥ 80% branch coverage
- [ ] Integration tests: ≥ 10 full e2e cycles
- [ ] Documentation: README + API comments
- [ ] Performance: Latency P95 < 2.5s, CPU < 60%
- [ ] Code review + approval (2 reviewers)
- [ ] Commit + branch pushed

---

**Créé**: 2026-04-30  
**Roadmap**: [docs/03-delivery/roadmap.md](../roadmap.md)  
**Sprint**: [docs/03-delivery/sprint-2-weeks.md](../sprint-2-weeks.md)
