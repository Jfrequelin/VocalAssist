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
3. Sinon encapsulation dans une enveloppe canonique firmware `AssistantPacket` avec `kind` et `payload` type.
4. Envoi au serveur du format canonique ou de son mapping compatible (`EdgeAudioRequest` pour l'audio historique).
5. Serveur route local intent ou Leon en fonction du `kind` recu puis produit une reponse dans la meme abstraction.
6. Edge joue audio localement et expose les controles stop/pause/volume.

## Abstraction echange de donnees

Le firmware utilise une couche unique d'echange pour normaliser les donnees issues des HAL:

- `audio`: microphone, playback, transport audio
- `image`: rendu LCD, captures ou assets d'interface
- `text`: transcription, messages UI, reponses courtes
- `variable`: etats runtime (mute, battery_pct, ui_state, wifi_rssi)
- `binary`: payload technique ou extension future

Cette abstraction evite les contrats ad hoc par peripherique et permet:
- de garder un pipeline uniforme cote firmware;
- de simplifier le routage cote assistant;
- de faire evoluer les peripheriques (ecran, tactile, telemetrie) sans redefinir un protocole complet.

## Capacites hardware exploitable sur la cible retenue

- ecran LCD tactile pour retour visuel local
- microphone(s) embarque(s) pour capture edge
- sortie audio locale pour TTS
- batterie + charge pour autonomie
- RTC pour fonctions temporelles futures
- TF pour stockage local futur

## Etat actuel d'exploitation logicielle

- deja modele: audio edge, wake word, VAD minimal, TTS locale, LED/mute/bouton, reconnexion simple
- abstraction d'echange canonique maintenant modelee cote firmware Rust pour audio, image, texte, variable et binaire
- non encore consommee completement cote assistant Python: image, variable, binaire generique
- non encore modele dans ce depot: ecran, tactile, batterie, RTC, TF comme fonctions applicatives completes
