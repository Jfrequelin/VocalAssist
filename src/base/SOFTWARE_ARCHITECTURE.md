# Architecture logicielle de la base edge

## Objectif

Definir une structure logicielle claire pour la base ESP32-S3 afin de:
- capter l'audio local,
- appliquer l'activation locale (wake word + filtre vocal),
- envoyer les requetes au serveur assistant,
- gerer les etats appareil (idle, listening, sending, speaking, muted, error),
- rester robuste aux erreurs reseau.

## Contrat reseau avec le serveur assistant

Endpoint principal:
- POST /edge/audio

Payload JSON attendu:
- correlation_id: string
- device_id: string
- timestamp_ms: int
- sample_rate_hz: int
- channels: int
- encoding: string
- audio_base64: string

Reponse attendue:
- HTTP 2xx: statut accepte, eventuellement un champ reply (texte a lire)
- HTTP 4xx: payload invalide, pas de retry automatique
- HTTP 5xx/429: erreur temporaire, retry avec backoff

## Modules software

- src/base/config.py
  - Configuration runtime de la base (device_id, URL serveur, wake_word, timeout, retries).
- src/base/contracts.py
  - Contrats de donnees reseau (EdgeAudioRequest, EdgeAudioResponse).
- src/base/state_machine.py
  - Machine a etats de l'appareil edge.
- src/base/transport.py
  - Client HTTP resilient vers le serveur assistant.
- src/base/runtime.py
  - Orchestrateur principal du flux audio vers backend.
- src/base/interfaces.py
  - Interfaces minimales pour injection d'implementation (transport, playback).

## Flux d'execution

1. Le runtime recoit un transcript et des octets audio.
2. Le runtime applique les gardes locales:
   - mute actif,
   - filtre vocal minimal,
   - wake word,
   - commande non vide.
3. Si accepte, creation du payload reseau standardise.
4. Envoi au serveur assistant avec retries pour erreurs temporaires.
5. Si reponse avec reply, playback local optionnel.
6. Retour a l'etat idle (ou muted).

## Machine a etats

- idle: pret a ecouter.
- listening: activation en cours.
- sending: envoi backend.
- speaking: restitution locale.
- muted: micro neutralise.
- error: echec interaction.

Transitions principales:
- idle -> listening -> sending -> speaking -> idle
- idle/listening/sending/speaking -> muted
- sending -> error
- error -> idle (sur interaction suivante)

## Separation des responsabilites

- Runtime: decision metier edge et orchestration.
- Transport: communication reseau pure.
- State machine: verite unique de l'etat appareil.
- Playback: sortie audio locale injectable (mock/reel).

## Plan d'integration embarquee

Phase 1 (simulation locale deja possible):
- runtime + transport + tests unitaires.

Phase 2 (bridge materiel):
- brancher capture micro I2S,
- brancher playback DAC/amp,
- brancher LED/ecran/touch sur la state machine.

Phase 3 (durcissement):
- telemetrie edge,
- watchdog,
- buffering court anti-coupure reseau,
- profils energie (actif/degrade).
