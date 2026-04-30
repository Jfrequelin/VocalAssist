# Architecture Edge + Serveur

## Principe global

- Edge: interaction temps reel et commandes locales critiques.
- Serveur local: STT/TTS avance, orchestration, Leon, integrations domotiques.

## Responsabilites Edge

- wake word local,
- capture audio + VAD,
- commandes locales prioritaires:
  - stop,
  - mute,
  - volume +/-,
  - extinction/restart logique,
- lecture locale TTS/streaming,
- mode degrade local si serveur indisponible.

## Responsabilites Serveur

- transcription STT,
- interpretation intent + slots,
- fallback Leon pour demandes complexes,
- execution actions via Home Assistant,
- generation TTS,
- observabilite et politiques de securite.

## Flux runtime

1. Wake word detecte sur edge.
2. Commande locale critique? Execution immediate.
3. Sinon envoi audio/texte au serveur.
4. Serveur route local intent ou Leon.
5. Serveur renvoie reponse + action eventuelle.
6. Edge joue audio localement et expose les controles stop/pause/volume.
