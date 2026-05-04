# Resultats campagne terrain edge - 2026-05-02

## Contexte d'execution

- Mode principal: testbench HTTP avec peripheriques mock
- Backend: docker compose local (`assistant-backend`, `leon-mock`, `ha-mock`)
- Completion FT-07/FT-08: prototype edge (commande `/button` disponible)

## Preuves

- Log nominal HTTP: `data/field-test-logs/ft-http-nominal.log`
- Snapshot nominal HTTP: `data/field-test-logs/ft-http-nominal.snapshot.json`
- Log backend down: `data/field-test-logs/ft-http-backend-down.log`
- Snapshot backend down: `data/field-test-logs/ft-http-backend-down.snapshot.json`
- Log reprise backend: `data/field-test-logs/ft-http-backend-recovery.log`
- Snapshot reprise backend: `data/field-test-logs/ft-http-backend-recovery.snapshot.json`
- Log controles prototype edge: `data/field-test-logs/ft-prototype-edge-controls.log`

## Resultats FT-01 a FT-08

- FT-01 Nominal reseau stable: PASS
  - Observation: `status=accepted`, `intent=light`, `source=local`.

- FT-02 Bruit ambiant sans wake word: PASS
  - Observation: rejet local `wake_word_missing`.

- FT-03 Wake word sans commande: PASS (variant)
  - Observation: rejet local `vad_rejected_low_voice` (equivalent fonctionnel: non envoi backend).

- FT-04 Backend indisponible: PASS
  - Observation: `reason=backend_rejected`, etat erreur, aucun crash.

- FT-05 Reprise apres backend retabli: PASS
  - Observation: apres redemarrage backend, requete acceptee (`status=accepted`, `source=leon`).

- FT-06 Wi-Fi faible/instable: NON EXECUTE
  - Raison: necessite injection reseau degradee (latence/pertes) non simulee dans cette passe.

- FT-07 Mode muet actif: PASS
  - Observation (prototype edge): payload envoye et accepte, restitution TTS supprimee (`muet`).

- FT-08 Coupure utilisateur bouton: PASS
  - Observation (prototype edge): commande `/button` appliquee, interaction stoppee, `event=button_pressed`.

## Actions restantes recommandees

- Executer FT-06 avec un profil reseau degrade (tc/netem) pour mesurer retries reels.
- Rejouer un passage complet avec micro/speaker systeme (pas mock) pour valider la chaine acoustique Linux.

## Execution checklist operationnelle (run commande)

- Date: 2026-05-02
- Checklist lancee: `doc/edge-field-checklist.md`

Etapes executees:

- Preparation audio capture: `arecord -l` -> OK (cartes detectees)
- Preparation audio playback: `aplay -l` -> OK (cartes detectees)
- Preparation Python venv: `./.venv/bin/python --version` -> OK (`Python 3.13.5`)
- Backend HTTP + smoke-test: `docker compose up -d --build` puis `./scripts/smoke-test.sh` -> OK
- Lancement operationnel systeme: `./scripts/run_edge_field_profile.sh http` -> BLOQUE capture ALSA
  - Erreur observee: `arecord: set_params:1398: Nombre de canaux non disponible`
  - Effet: `empty_audio` (pas d'envoi backend)
- Validation fonctionnelle fallback mock: PASS (accepted sur `/edge/audio`)

Artefacts de ce run:

- `data/field-test-logs/ft-http-system-checklist.log`
- `data/field-test-logs/ft-http-system-checklist.snapshot.json`
- `data/field-test-logs/ft-http-mock-checklist.log`
- `data/field-test-logs/ft-http-mock-checklist.snapshot.json`
