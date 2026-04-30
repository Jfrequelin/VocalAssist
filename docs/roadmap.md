# Roadmap Assistant Vocal

> Legacy: document conserve pour historique.
> Source canonique: `docs/03-delivery/roadmap.md`.

Roadmap detaillee orientee Leon:
- docs/roadmap-leon-assistant-vocal.md

Specification complete du projet:
- docs/specification-projet-complete.md

## Avancement actuel

- Phase 1: terminee
- Phase 2: en cours avance (scenarios versionnes, intents etendus, metriques de simulation, tests unitaires)
- Phase 3: a demarrer (branchements STT/TTS reels)

## Phase 1 - Definition

- Personas: utilisateur maison connectee, freelance, famille.
- Cas d'usage prioritaires:
  - Informations rapides (heure, date, meteo).
  - Commandes domotiques de base.
  - Lancement de routines simples.
- Contraintes:
  - Local-first quand possible.
  - Donnees minimales et transparence utilisateur.

## Phase 2 - Simulation

- Etendre les intents:
  - Rappels
  - Agenda
  - Controle multimedia
- Ajouter un fichier de scenarios de tests.
- Mesurer:
  - Taux de reconnaissance d'intention.
  - Temps de reponse moyen.

### Statut implementation

- Fichier de scenarios ajoute: `data/simulation_scenarios.json`
- Intents ajoutes: `reminder`, `agenda`
- Sortie de simulation avec score global de reconnaissance
- Base de tests unitaires en place dans `tests/`

## Phase 3 - Prototype vocal

- Entrée audio:
  - Wake word (Porcupine ou equivalent)
  - STT (Whisper/Vosk)
- Sortie audio:
  - TTS local (Coqui/pyttsx3)
- Integrations:
  - API meteo reelle
  - Webhooks domotiques

## Critere de passage en demo

- 10 commandes vocales executes sans crash.
- Au moins 70% de commandes reconnues correctement sur un jeu de test.
- Documentation d'installation reproductible.
