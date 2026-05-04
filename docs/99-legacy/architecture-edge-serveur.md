# Architecture cible assistant vocal (Edge + Serveur central)

> Legacy: document conserve pour historique.
> Sources canoniques:
> - `docs/02-architecture/system-architecture.md`
> - `docs/02-architecture/interfaces-and-contracts.md`

Date: 2026-04-30
Contexte: assistant vocal type Alexa avec moteur Leon

## 1. Objectif

Definir une architecture robuste, evolutive et local-first en separant:
- Edge: objet physique (enceinte vocale)
- Serveur central: intelligence, orchestration, integrations

## 2. Principes d'architecture

- Local-first pour latence et resilence.
- Wake word local obligatoire sur chaque edge (pas de dependance serveur pour le reveil).
- Privacy by design (donnees minimales, retention courte).
- Fallback progressif (local -> serveur -> mode degrade).
- Contrats API explicites et versionnes.
- Observabilite de bout en bout (audio -> intent -> action -> reponse).

## 3. Repartition des responsabilites

## 3.1 Edge (objet physique type Alexa)

Reference prototype V1:
- Module ESP32-S3 avec haut-parleur integre (choix valide pour le premier prototype).
- L'intelligence avancee reste delocalisee sur le serveur local.

Responsabilites:
- Wake word detection.
- VAD (voice activity detection) et capture micro.
- Pre-traitement audio (gain, reduction bruit basique).
- Commandes systeme critiques locales:
  - stop
  - mute micro
  - annule
  - extinction appareil
  - redemarrage appareil
  - volume plus/moins
- Commandes basiques locales obligatoires (executables sans serveur):
  - "eteins-toi" -> extinction controlee
  - "redemarre" -> redemarrage controle
  - "coupe le micro" -> mute immediat
  - "stop" -> interruption immediate TTS/traitement
- STT/TTS local de secours.
- Lecture locale de flux audio (streaming) sur instruction du serveur.
- Gestion UI device:
  - LEDs
  - boutons physiques
  - volume
- Cache local de contexte court (session courante).
- Mode offline degrade.

Contraintes:
- Latence ultra courte.
- Tolerance aux pannes reseau.
- Consommation CPU/RAM maitrisee.
- Support d'un mode push-to-talk de secours si wake word instable en phase de calibration.

## 3.2 Serveur central

Responsabilites:
- Moteur Leon principal (raisonnement et generation).
- Orchestration intentions/actions multi-etapes.
- Memoire long terme et profils utilisateurs.
- Integrations:
  - Home Assistant
  - APIs externes
  - routines et planification
- Observabilite centrale:
  - logs structures
  - metriques
  - traces
- Gouvernance:
  - politiques de securite
  - controle de versions
  - deploiements

Contraintes:
- Disponibilite elevee.
- Timeouts stricts et retries bornes.
- Traiter plusieurs devices simultanement.

## 4. Flux principal (runtime)

1. Edge detecte wake word.
2. Edge capture audio utilisateur.
3. Edge verifie d'abord le set des commandes basiques locales.
4. Si commande locale reconnue, execution immediate sans appel serveur.
5. Sinon, Edge tente route locale rapide (intent deterministe).
6. Si intent inconnu ou complexe, Edge appelle serveur.
7. Serveur (Leon) decide:
   - reponse textuelle
   - action domotique
   - besoin de confirmation
8. Edge joue reponse TTS.
9. Edge execute action locale autorisee ou relaie execution distante.
10. En cas d'echec serveur: mode degrade local et maintien des commandes basiques locales.

## 4.1 Flux de lecture audio locale (streaming)

1. Le serveur envoie a l'edge un ordre de lecture (`play_stream`) avec URL et metadata.
2. L'edge ouvre le flux, initialise un buffer local et demarre la lecture.
3. Pendant la lecture, les commandes locales prioritaires restent actives:
  - stop
  - pause/reprise
  - volume plus/moins
  - mute micro
4. Si coupure reseau, l'edge tente un retry borne puis stoppe proprement avec message utilisateur.
5. Le serveur reste responsable de la selection du contenu, l'edge de la lecture temps reel.

## 5. Contrat API Edge <-> Serveur

## 5.1 Requete (exemple)

```json
{
  "api_version": "v1",
  "device_id": "edge-salon-01",
  "session_id": "sess-20260430-001",
  "timestamp": "2026-04-30T14:30:00Z",
  "input": {
    "text": "allume la lumiere du salon",
    "lang": "fr-FR",
    "stt_confidence": 0.92
  },
  "context": {
    "room": "salon",
    "user_id": "user-001",
    "is_offline_mode": false
  }
}
```

## 5.2 Reponse (exemple)

```json
{
  "api_version": "v1",
  "request_id": "req-12345",
  "result": {
    "source": "leon",
    "intent": "light_on",
    "answer_text": "J'allume la lumiere du salon.",
    "action": {
      "type": "home_assistant_call",
      "target": "light.salon",
      "payload": {"state": "on"},
      "requires_confirmation": false
    },
    "confidence": 0.89
  },
  "policy": {
    "cache_ttl_seconds": 30,
    "allow_local_repeat": true
  }
}
```

## 5.3 Regles de communication

- Timeout total par requete: 1500 ms cible, 2500 ms max.
- Retries: 1 retry max avec backoff court.
- Circuit breaker: ouverture apres N echecs consecutifs.
- Idempotence requise pour les actions domotiques.

## 5.4 Contrat commande audio (exemple)

```json
{
  "api_version": "v1",
  "request_id": "req-audio-001",
  "result": {
    "source": "leon",
    "intent": "play_audio_stream",
    "answer_text": "Je lance la lecture.",
    "action": {
      "type": "play_stream",
      "stream": {
        "url": "https://example.org/stream.mp3",
        "codec": "mp3",
        "buffer_ms": 1200
      },
      "policy": {
        "retry_count": 1,
        "retry_backoff_ms": 400,
        "allow_local_controls": true
      }
    }
  }
}
```

## 6. Securite

- TLS sur tous les echanges Edge <-> Serveur.
- Auth mutuelle device/service (token ou certificat).
- Permissions par type d'action (RBAC simplifie).
- Chiffrement des secrets au repos.
- Journaux sans audio brut par defaut.
- Rotation reguliere des credentials.

## 7. Donnees et vie privee

- Donnees minimales collectees.
- Retention courte des transcriptions.
- Opt-in explicite pour telemetry et analytics.
- Possibilite d'effacement complet des donnees utilisateur.

## 8. Observabilite et KPI

Metriques minimales:
- Latence E2E (P50, P95)
- Taux de succes wake word
- Taux de reconnaissance intention correcte
- Taux d'erreur API serveur
- Taux de fallback mode degrade
- Taux de demarrage lecture flux reussi
- Temps de demarrage de lecture (stream start latency)
- Nombre moyen de coupures audio par heure

Logs traces:
- Correlation ID unique par interaction.
- Trace complete: wake -> stt -> route -> action -> tts.

## 9. Modes de fonctionnement

- Mode normal: local + serveur.
- Mode degrade reseau: local uniquement, avec commandes basiques toujours actives.
- Mode maintenance: serveur lecture seule, actions sensibles bloquees.

## 9.1 Validation fonctionnelle - lecture locale flux audio

Fonctionnalite validee si:
- L'edge lit un flux audio distant sans relais PCM via serveur.
- Les commandes locales `stop`, `pause`, `resume`, `volume +/-` repondent en < 300 ms.
- En cas de perte reseau, la lecture se termine proprement sans crash.
- Le serveur ne transporte pas le flux audio, uniquement les ordres de controle.

## 10. Evolution prevue

- Multi-room avec satellites audio.
- Multi-utilisateur avec profils vocaux.
- Federation de plusieurs serveurs centraux (haute disponibilite).
- Optimisation edge AI (STT/TTS plus performants localement).
