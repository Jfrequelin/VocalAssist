# STM32 Macros Roadmap - Pipeline Vocal Complet

**Status**: 🎯 Planning Phase  
**Created**: 2026-05-01  
**Objective**: Implémenter le pipeline vocal complet côté STM32 en prenant les interfaces et spécifications du serveur assistant

---

## Vue d'Ensemble

Ces macros couvrent l'implémentation complète du firmware STM32 pour supporter les interactions vocales depuis la capture audio jusqu'à la synthèse vocale et le feedback utilisateur.

Les interfaces are **définies côté assistant** et doivent être **répliquées côté STM32** avec adaptation au contexte embedded.

---

## 🔓 Contrainte: Solutions Open Source

**Directive**: Utiliser exclusivement des solutions open source pour tous les composants critiques.

### Stack Open Source Requis

| Composant | Solution | Licence | Raison |
|-----------|----------|---------|--------|
| **Language** | Rust | MIT/Apache 2.0 | Sécurité mémoire, ecosystem embedded |
| **Audio Synthesis** | Piper (Rhasspy) | MIT | Local, français, embarquable, gratuit |
| **Audio Capture** | Standard I2S + HAL | MIT/Apache | STM32 open drivers |
| **Wake Word** | PocketSphinx / Porcupine alternative | BSD / MIT | Décentralisé, français |
| **VAD** | webrtcvad ou WebRTC | BSD | Qualité OpenAI, gratuit |
| **HTTP Client** | smoltcp / esp-idf | MIT/Apache | Léger, bare-metal capable |
| **Build System** | Cargo | MIT/Apache | Rust standard, gratuit |
| **Testing** | Rust tests built-in + criterion | MIT/Apache | Gratuit, zéro dépendance |
| **RTOS** | FreeRTOS | MIT | Si needed, ultra-lean |
| **HAL** | stm32l4xx-hal / stm32h7xx-hal | MIT/Apache | Community-maintained |

### ✅ Approuvés pour MACRO-006 à MACRO-013

**Embedded Rust Ecosystem**:
- `cortex-m` (MIT) - ARM Cortex-M support
- `embedded-hal` (MIT/Apache) - Trait abstractions
- `heapless` (MIT) - No_std collections
- `defmt` (MIT) - Embedded formatting
- `smoltcp` (MIT) - Bare-metal TCP/IP
- `esp-idf` (variations) - ESP32 support
- `stm32l4xx-hal` (MIT) - STM32L4 HAL

**Audio/NLP Stack**:
- `piper-tts` Rust bindings (tbd, but Piper is MIT)
- `rubato` (MIT) - Audio resampling
- `lewp-rt` alternatives pour compression

### ❌ À Éviter Absolument

- Google Cloud Speech API (propriétaire, cloud-only)
- Azure Speech Services (propriétaire)
- Nuance Dragon (propriétaire, coûteux)
- Proprietary RTOS (QNX, Integrity)
- Vendor lock-in (AWS IoT Core only, Azure only)

### 📋 Validation pour chaque ajout de dépendance

Avant import dans Cargo.toml pour STM32:

```bash
# 1. Vérifier licence
cargo tree | grep -E "MIT|Apache|BSD|GPL"
# ALL doivent être compatible

# 2. Vérifier no_std support
cargo build --release --no-default-features
# ✅ Compile sans std library

# 3. Vérifier taille ajoutée
cargo build --release --target thumbv7em-none-eabihf
ls -lh target/thumbv7em-none-eabihf/release/
# ❌ Si + 100KB par dépendance, questionner la nécessité

# 4. Vérifier activité
gh repo view <owner>/<crate> --json updatedAt
# ✅ Maintenance < 3 mois, pas délaissé
```

---

## Macros STM32 (MACRO-006 → MACRO-013)

### MACRO-006: Transport Audio et Synchronisation Réseau (#149)
**Priority**: ⭐⭐⭐⭐⭐ (Blocker)  
**Status**: `not-started`

Implémente le transport audio du STM32 vers le serveur assistant avec le contrat API défini dans `src/assistant/edge_backend.py`.

**Payload HTTP/JSON**:
```json
{
  "correlation_id": "uuid",
  "device_id": "device-id",
  "timestamp_ms": 1234567890,
  "sample_rate_hz": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "audio_base64": "base64_encoded_audio"
}
```

**Endpoint**: `POST /edge/audio`

**Dépendances**:
- I2S audio capture (PCM5101 DAC)
- WiFi drivers + HTTP client TLS
- RTC/NTP pour timestamps
- Retry + queue persistence

---

### MACRO-007: Gestion d'État et Contrôle LED (#150)
**Priority**: ⭐⭐⭐⭐⭐ (Blocker)  
**Status**: `not-started`

Implémente le contrôle d'état device et la gestion visuelle via LED RGB, en répliquant l'API définie dans `src/assistant/edge_device.py`.

**State Model**:
```python
EdgeDeviceState:
  - muted: bool
  - led_state: str  # idle|listening|sending|speaking|muted|error
  - interaction_active: bool
  - last_event: str
```

**LED States avec couleurs et animations**:
| État | Couleur | Animation | Sens |
|------|---------|-----------|------|
| idle | Vert | Fixe | Prêt |
| listening | Bleu | Clignotant 1Hz | Écoute active |
| sending | Jaune | Clignotant 2Hz | Upload audio |
| speaking | Orange | Clignotant 1.5Hz | TTS actif |
| muted | Rouge | Fixe | Muet |
| error | Rouge | Clignotant 0.5Hz | Erreur |

**Contrôles Requis**:
- `set_mute(enabled)` → change LED
- `toggle_mute()` → bascule
- `start_interaction()` → listening
- `mark_sending()`, `mark_speaking()`, `mark_error()`
- `finish_interaction()`, `press_button()`

---

### MACRO-008: Intents Audio Système et Contrôle Média (#151)
**Priority**: ⭐⭐⭐⭐ (High)  
**Status**: `not-started`

Implémente les intents système qui sont traités **localement sans délai réseau** et sans consultation du serveur.

**Intents Système** (détectés + traités localement):

1. **stop_media** (Priority 100)
   - Mots-clés: "stop la musique", "arrete la musique", "pause musique"
   - Action: Arrêt immédiat du TTS/média, signal STOP au DAC

2. **mute** (Priority 95)
   - Mots-clés: "mute", "coupe le son", "mode muet", "silence"
   - Action: Toggle mute, LED rouge, amplifier désactivé

3. **volume** (Priority 90)
   - Mots-clés: "volume", "augmente le son", "baisse le son"
   - Action: Détection direction, ajustement DAC 0-100, feedback auditif

**Traitement local sans latence réseau**:
- Intent parser conforme à `src/assistant/intents.py`
- Normalisation texte + décomposition diacritiques
- Exécution immédiate (< 500ms)

---

### MACRO-009: Intents Informatifs et Réponses Locales (#152)
**Priority**: ⭐⭐⭐⭐ (High)  
**Status**: `not-started`

Implémente les intents informatifs avec réponses rapides générées localement.

**Intents Informatifs** (Priority 50):

1. **time** → "Il est HH:MM" (via RTC)
2. **date** → "Nous sommes le DD/MM/YYYY" (via RTC)
3. **weather** → Fetch API + synthèse réponse
4. **temperature** → Capteur ou serveur local
5. **system_help** (Priority 80) → Réciter commandes disponibles

**Features**:
- RTC synchronisé via NTP
- HTTP client pour APIs externes (OpenWeatherMap)
- Cache local (météo, données)
- Timeout réseau: 2s max
- Tous les résultats sont lus via TTS

---

### MACRO-010: Intents de Contrôle Domotique (#153)
**Priority**: ⭐⭐⭐⭐ (High)  
**Status**: `not-started`

Implémente les intents de contrôle qui routent vers le serveur assistant ou GPIO local.

**Intents de Contrôle** (Priority 50):

1. **light** → Parse pièce, relay vers serveur ou GPIO local
2. **music** → Parse artiste/album, envoi serveur
3. **reminder** → Parse temps/date, stockage serveur
4. **agenda** → Requête serveur calendar
5. **restart** (Priority 85) → Soft reset avec feedback
6. **exit** (Priority 10) → Arrêt pipeline

**Features**:
- Intent parsing + slot extraction
- Routing HTTP vers assistant ou GPIO
- Feedback auditif TTS pour tous les intents
- Retry logic + error handling

---

### MACRO-011: Synthèse Vocale (TTS) et Playback Audio (#154)
**Priority**: ⭐⭐⭐⭐⭐ (Blocker)  
**Status**: `not-started`

Implémente le moteur de synthèse vocale locale (Piper) et la lecture des réponses audio.

**Composants**:

1. **TTS Local Français (Piper)**
   - Piper Rust binding pour ARM Cortex-M
   - Modèle français embarqué ou téléchargeable
   - Synthèse < 500ms pour phrase standard
   - Caching pour réutilisation

2. **Audio Playback (PCM5101 DAC)**
   - I2S driver pour output
   - Buffer/FIFO gestion
   - Volume control 0-100 intégré
   - Smooth ramping, mute support

3. **Feedback Auditif Court**
   - Beep/click (confirmation)
   - Tone errors (buzzer pour erreurs)

**Cas d'Usage**:
- Synthèse réponse heure: < 800ms total
- Synthèse commande light: < 1s
- Error handling: fallback short feedback

---

### MACRO-012: Résilience et Gestion d'Erreurs Réseau (#155)
**Priority**: ⭐⭐⭐⭐ (High)  
**Status**: `not-started`

Implémente la robustesse et la tolérance aux pannes du système.

**Scénarios de Résilience**:

1. **Perte WiFi**
   - Queue locale d'audio en attente
   - Reconnection auto avec backoff exponentiel
   - Timeout 30-60s avant abandon
   - LED error clignotement

2. **Assistant Indisponible**
   - HTTP timeout: 5s
   - Retry 3x avec délai exponentiel
   - Fallback: exécuter local intent si applicable

3. **Audio Capture Failure**
   - Détection corruption PCM
   - Mark error state
   - Continue listening après recovery

4. **TTS Timeout**
   - Piper timeout: 3s
   - Fallback: beep + message
   - Retry sur prochaine synthèse

5. **Débordement Mémoire**
   - Monitor heap usage
   - Cleanup buffer ancien si élevé
   - Disable caching TTS temporairement

**Persistence Locale**:
- EEPROM: config WiFi, volume, device_id
- Logging circulaire en SRAM (100 events récents)
- Error code system

---

### MACRO-013: Pipeline Complet et Validation End-to-End (#156)
**Priority**: ⭐⭐⭐⭐⭐ (Final Integration)  
**Status**: `not-started`

Intègre tous les composants en un pipeline vocal fonctionnel avec validation complète.

**Pipeline Complet**:
```
Audio Capture (I2S)
    ↓
Wake Word Detection (process_transcript)
    ↓
Intent Recognition & Routing
    ├─ Local Intent → Execute + TTS + Playback
    └─ Remote Intent → Transport + Await Response + TTS + Playback
    ↓
Error Handling & Resilience
    ↓
Return to Idle
```

**Test Cases End-to-End**:

1. **Local Intent** - Time Query (< 2s)
   - User: "Quelle heure est-il?"
   - System: Wake word → intent=time → RTC → TTS → Playback
   
2. **Remote Intent** - Music Control (< 5s)
   - User: "Mets de la musique"
   - System: Wake word → intent=music → transport → TTS → Playback

3. **System Control** - Mute (< 500ms)
   - User: "Silence"
   - System: Wake word → mute toggle → LED red → Beep

4. **Error Recovery** - WiFi Down (< 10s)
   - WiFi desactivé
   - System: Retry loop → mark_error → Feedback → Return idle

5. **Streaming** - Long Interaction
   - User: "Raconte-moi une histoire"
   - System: Stream avec interruption possible via button

**Validation Matérielle**:
- Waveshare ESP32-S3 Touch LCD 1.85"
- STM32 coprocessor
- LED RGB + GPIO button
- WiFi + Bluetooth
- Audio I2S + DAC

---

## Dépendances Inter-Macros

```
MACRO-013 (Pipeline Complet)
├── MACRO-006 (Transport Audio)
├── MACRO-007 (État & LED)
├── MACRO-008 (Intents Système)
├── MACRO-009 (Intents Informatifs + RTC)
├── MACRO-010 (Intents Domotique)
├── MACRO-011 (TTS & Playback)
└── MACRO-012 (Résilience & Erreurs)
```

**Ordre Recommandé d'Implémentation**:
1. MACRO-007 (État/LED - fondations UI)
2. MACRO-006 (Transport - fondations réseau)
3. MACRO-008 (Intents système - feedback rapide)
4. MACRO-011 (TTS - output audio)
5. MACRO-009 (Intents informatifs - RTC)
6. MACRO-010 (Intents domotique - HTTP)
7. MACRO-012 (Résilience - robustesse)
8. MACRO-013 (Pipeline complet - validation)

---

## Interfaces Répliquées depuis Assistant

### From `src/assistant/edge_backend.py`
- Validation payload audio
- Endpoint `/edge/audio`
- Error codes: `missing_fields`, `invalid_*`, `empty_audio`

### From `src/assistant/edge_device.py`
- `EdgeDeviceState` dataclass
- `EdgeDeviceController` methods
- State transitions: idle → listening → sending → speaking → idle
- LED mapping: state → couleur/animation

### From `src/assistant/intents.py`
- Intent registry avec priority
- Keyword matching (multi-word, word boundary)
- Text normalization (lowercase, NFKD decomposition, diacritics removal)
- Intent parsing + slot extraction

### From `src/base/firmware/stm32-rust/src/lib.rs`
- `process_transcript()` function - wake word + VAD + command detection
- `Runtime` state machine
- `Config` validation

---

## Ressources et Références

- **Hardware**: [Waveshare ESP32-S3 1.85 Round LCD](https://www.amazon.fr/dp/B0F18D8S27)
- **Firmware Rust**: `src/base/firmware/stm32-rust/`
- **Python Architecture**: `src/assistant/` et `src/base/`
- **Tests**: `tests/` pour patterns de test

---

## KPIs et Success Criteria

### Fonctionnels
- ✅ All 8 macros implemented
- ✅ 100+ tests for MACRO-006 through MACRO-012
- ✅ 50+ end-to-end integration tests for MACRO-013
- ✅ Memory usage < 2MB heap
- ✅ Code size < 4MB
- ✅ Latency: typical interaction < 5s
- ✅ WiFi reconnection < 30s
- ✅ Zero critical errors in 1000-cycle stress test
- ✅ Documentation + deployment guide

### Open Source Compliance (OBLIGATOIRE)
- ✅ **100% composants open source** - MIT/Apache/BSD/GPL compatible
- ✅ **Zéro dépendance propriétaire** - pas de cloud-only, pas de vendor lock-in
- ✅ **Audit de licences** - `cargo tree` montre toutes les licences compatibles
- ✅ **Respect SPDX** - toutes les dépendances répertoriées avec identifiant SPDX
- ✅ **No Freemium** - aucun service "gratuit avec plan payant obligatoire"
- ✅ **Auditabilité** - tout le code critique auditable par la communauté

---

## Timeline Estimate

| Macro | Effort | Estimate | Status |
|-------|--------|----------|--------|
| MACRO-006 | 40h | 1 week | `not-started` |
| MACRO-007 | 30h | 4 days | `not-started` |
| MACRO-008 | 35h | 5 days | `not-started` |
| MACRO-009 | 40h | 1 week | `not-started` |
| MACRO-010 | 40h | 1 week | `not-started` |
| MACRO-011 | 50h | 1.5 weeks | `not-started` |
| MACRO-012 | 30h | 4 days | `not-started` |
| MACRO-013 | 50h | 1.5 weeks | `not-started` |
| **TOTAL** | **315h** | **~8-9 weeks** | - |

---

**Last Updated**: 2026-05-01  
**Author**: GitHub Copilot  
**Next Step**: Start MACRO-007 for state/LED foundation
