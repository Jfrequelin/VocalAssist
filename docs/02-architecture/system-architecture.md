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
- affichage local sur ecran,
- interaction tactile locale minimale,
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

## Capacites hardware exploitable sur la cible retenue

- ecran LCD tactile pour retour visuel local
- microphone(s) embarque(s) pour capture edge
- sortie audio locale pour TTS
- batterie + charge pour autonomie
- RTC pour fonctions temporelles futures
- TF pour stockage local futur

## Etat actuel d'exploitation logicielle

- deja modele: audio edge, wake word, VAD minimal, TTS locale, LED/mute/bouton, reconnexion simple
- non encore modele dans ce depot: ecran, tactile, batterie, RTC, TF
