# MVP Status - Statut du Produit Minimum Viable

**Date**: Mai 2026  
**État**: MVP consolidé et validé (396/396 tests passants)

## Macros Couvertes

### ✅ MACRO-001: Activation et session vocale
**État**: COMPLÉTÉ (T1, T2, T3, T4 implémentés et validés)

- **T1 - Activation**
  - ✅ `WakeWordHandler`: Extraction unifiée du wake word
  - ✅ Support multi-mode (terminal et vocal)
  - ✅ Normalisation (multi-espaces, case-insensitive)
  - Tests: 10 ✅

- **T2 - Messages Système**
  - ✅ `SystemMessages`: Catalogue centralisé
  - ✅ Reemploi dans terminal et pipeline vocal
  - ✅ Élimination 4 duplications
  - Tests: 81 ✅

- **T3 - Session et Timeouts**
  - ✅ `SessionManager`: Lifecycle explicite (ACTIVE → EXPIRED → CLOSED)
  - ✅ Timeouts configurables par mode
  - ✅ Reprise de session après inactivité
  - ✅ Enregistrement d'activité pour étendre les timeouts
  - ✅ Intégration dans `prototype.py` et `prototype_voice.py`
  - ✅ Documentation du cycle conversationnel
  - Tests: 7 ✅

- **T4 - Tests Conversationnels**
  - ✅ Scénarios multi-étapes couverts
  - ✅ Validation des critères d'acceptation
  - ✅ Couverture via `test_simulation.py` et tests pipeline associés

### ✅ MACRO-007: Domotique et services externes
**État**: COMPLÉTÉ

- ✅ Provider pattern (Protocol-based abstraction)
- ✅ `HomeAssistantLightProvider`: Contrôle de lumière
- ✅ `WeatherProvider`: Météo dynamique
- ✅ `WebhookMusicProvider`: Musique
- ✅ `ProviderRegistry`: Factory avec env loading
- ✅ Intégration dans `intents.py`
- ✅ Fallback homogène
- Tests: 30+ ✅

### ✅ MACRO-008: Qualité, sécurité et pilotage
**État**: DÉJÀ IMPLÉMENTÉ (sessions antérieures)

- ✅ Logs structurés avec correlation IDs
- ✅ Circuit breaker pour Leon
- ✅ Validation et secrets (env-only)
- ✅ Tests de validation des tickets
- ✅ Sync GitHub (macro/epic generation)
- ✅ Backlog publishing

### ✅ Suivi backlog GitHub/local
**État**: aligné et fermé

- ✅ Backlog GitHub: 0 issue ouverte
- ✅ Synchronisation locale: `doc/tickets` et `.tickets-local` alignés
- ✅ Référence index: `doc/tickets/INDEX.md` (148 fermés / 0 ouverts)

## Fonctionnalités du MVP

### 1. Activation Vocale
- Wake word "nova" configurable
- Extraction de commande après activation
- Support de l'aide (nova aide)
- Support de la fermeture (nova stop)

### 2. Traitement d'Intent Local-First
- Intents: `light`, `weather`, `music`, `timestamp`, `exit`
- Slot extraction (pièce, ville, etc.)
- Fallback à Leon pour intents inconnus
- Circuit breaker sur Leon

### 3. Providers Externes
- Integration Home Assistant pour lumière
- Integration weather API pour météo
- Webhook générique pour musique
- Configuration env-based (stricte pour Leon)

### 4. Pipeline Vocal
- STT: Whisper (réel) ou mock
- TTS: Piper (réel) ou mock
- Timing metrics (STT/orchestrator/TTS)
- Gestion des erreurs moteur

### 5. Gestion de Session
- Création de session à l'activation
- Timeout inactivité configurable (terminal: 120s, vocal: 60s)
- Reprise automatique si inactivité < timeout
- Fermeture explicite via "exit"

### 6. Qualité
- 396 tests passants
- Correlatione IDs pour tous les appels
- Logs structurés avec source (local/leon/provider/fallback)
- Validation pre-commit (tickets, format)

## Validations Complétantes

### Couverture Fonctionnelle
```
Intent Coverage:
- light (local) ✅
- weather (local + provider) ✅
- music (provider) ✅
- timestamp (local) ✅
- temperature (local) ✅
- exit (local) ✅
- unknown (leon fallback) ✅

Modes:
- Terminal mode ✅
- Voice pipeline mode ✅

Scenarios:
- Wake word + command ✅
- Help request ✅
- Empty command after activation ✅
- Exit/stop ✅
- Unknown intents (Leon) ✅
- Provider unavailable (fallback) ✅
- Session timeout (auto-expiry) ✅
```

### Pylance Validation
- Tous les fichiers: 0 erreurs
- Type hints: Strict mode
- Imports: Utilisés et corrects

### Test Suite
```
Total: 396 tests
Status: 100% passing
Categories:
- Orchestrator et routage ✅
- Providers et fallback ✅
- Wake word et session manager ✅
- Pipeline vocal (STT/TTS/latence/erreurs) ✅
- Simulation/scénarios/intents/slots ✅
- Résilience, rétention, contexte et sync tickets ✅
```

## Commandes pour Démarrer

### Mode Terminal
```bash
python3 -m src.assistant.prototype
```

### Mode Vocal (STT/TTS simulé)
```bash
python3 -m src.assistant.prototype_voice
```

### Mode Vocal Réel (avec Whisper + Piper)
```bash
ASSISTANT_VOICE_ENGINE=real python3 -m src.assistant.prototype_voice
```

## Configuration Requise

### Variables d'Environnement (Obligations/Optionnelles)

**Obligatoires** (Leon - strict mode):
```bash
LEON_HTTP_API_URL=http://localhost:1337
LEON_PACKAGE_NAME="en"
LEON_MODULE_NAME="en"
LEON_ACTION_NAME="en"
```

**Optionnelles** (Providers):
```bash
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=<token>
WEATHER_PROVIDER_URL=https://api.weather.com/weather?city={CITY}
MUSIC_PROVIDER_URL=https://music.webhook.local/play
MUSIC_PROVIDER_BEARER_TOKEN=<token>
```

## Éléments Not in Scope (MVP)

- Stockage persistant de session
- Authentification utilisateur
- Apprentissage (machine learning)
- Multitâche simultané
- Personnalisation de réponses
- Intégration multi-provider (choix automatique)

## Prochaines Étapes (Post-MVP)

1. **Déploiement**: Dockeriser l'application
2. **Scalabilité**: Session storage (Redis/DB)
3. **Richesse**: Plus de providers, plus d'intents
4. **UX**: Interface web / mobile
5. **Intelligence**: Fine-tuning sur Leon
6. **Satellite**: Support ESP32-S3 (MACRO-006)
7. **Productivité**: Calendrier, TODO (MACRO-003)

## Validation Finale

✅ **MVP READY FOR PRODUCTION**

Tous les tickets publiés ont été traités et fermés côté GitHub.  
Le produit est déployable et fonctionnel sur les deux modes (terminal et vocal).  
La validation courante confirme une base stable pour la suite des itérations.

### Commits Finaux
- f7a62a4: Wake word handler + centralization
- ccc356a: System messages normalization
- aa65a0f: Session manager integration

**396 tests OK | 0 Pylance errors | 148 tickets fermés / 0 ouverts**
