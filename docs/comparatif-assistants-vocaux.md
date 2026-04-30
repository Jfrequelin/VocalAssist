# Comparatif des projets proches d'OpenVoiceOS

> Legacy: document conserve pour historique.
> Source canonique: `docs/05-research/assistant-benchmark.md`.

Date de reference: 2026-04-30

## 1) Projets compares

- OpenVoiceOS (OVOS)
- Mycroft Core
- Rhasspy
- Home Assistant Assist
- Leon
- Naomi

## 2) Tableau comparatif rapide

| Projet | Orientation | Offline / Privacy | Etat de maintenance (constate) | Integrations domotiques | Profil ideal |
|---|---|---|---|---|---|
| OpenVoiceOS | Plateforme assistant vocal open-source (successeur spirituel de Mycroft) | Forte orientation vie privee et local-first | Actif (commits recents, releases recentes) | Bonne (skills, ecosys. OVOS, compatibilites Mycroft) | Projet custom assistant vocal sur Linux/RPi |
| Mycroft Core | Ancienne base historique Mycroft | Possible en partie, mais backend historique present | Archive / non maintenu (repo read-only) | Historiquement bonne | Reference historique uniquement |
| Rhasspy | Assistant vocal offline par services (MQTT/Hermes/HTTP) | Tres fort offline / prive | Archive read-only (repo principal) | Tres bonne avec Home Assistant / Node-RED | Power users orientés local et pipelines audio |
| Home Assistant Assist | Assistant vocal integre a Home Assistant | Local possible + options cloud | Tres actif (ecosysteme HA) | Excellente (natif Home Assistant) | Maison connectee centree Home Assistant |
| Leon | Assistant personnel open-source modulaire (Node/Python) | Local possible, choix de providers | Actif (commits recents) | Moins centre domotique native qu'HA/OVOS | Assistant personnel generaliste et extensible |
| Naomi | Assistant vocal open-source issu de Jasper | Orientation open-source locale | Activite plus faible (commits anciens) | Plus limitee que HA/OVOS | Bricolage/prototypage OSS |

## 3) Points cles par projet

### OpenVoiceOS

- Positionnement: plateforme communautaire open-source pour interfaces vocales multi-appareils.
- Points forts:
  - Continuite de l'approche Mycroft avec evolution active.
  - Installable via Python, Docker, installer dedie, image Raspberry Pi.
  - Ecosysteme skills et possibilite d'integration LLM/persona.
- Vigilance:
  - Courbe d'apprentissage (architecture modulaire + ecosysteme).

### Mycroft Core

- Positionnement: projet historique qui a inspire beaucoup d'ecosystemes open voice.
- Constat 2026:
  - Repo `mycroft-core` archive (read-only) et explicitement non maintenu.
- Usage recommande:
  - Source d'inspiration / retro-compatibilite, pas base principale pour nouveau projet.

### Rhasspy

- Positionnement: suite de services offline, orientee intents/grammaires et interop MQTT/HTTP/WebSocket.
- Points forts:
  - Tres bon pour le local pur et la vie privee.
  - Bonne integrabilite Home Assistant / Node-RED.
- Constat 2026:
  - Repo principal archive (read-only), donc risque maintenance a moyen terme.

### Home Assistant Assist

- Positionnement: assistant vocal natif de l'ecosysteme Home Assistant.
- Points forts:
  - Integration domotique immediate et tres large base communautaire.
  - Support local ou cloud selon les choix de deploiement.
  - Outils et guides concrets (satellites ESPHome, wake words, personnalisation).
- Vigilance:
  - Si ton produit depasse la domotique, il faut ajouter une couche applicative supplementaire.

### Leon

- Positionnement: assistant personnel OSS moderne, oriente outils/memoire/agent.
- Points forts:
  - Projet tres actif.
  - Architecture modulaire riche (skills, tools, bridges), bonne base experimentation IA.
- Vigilance:
  - Moins oriente "smart home first" que Home Assistant Assist / OVOS.
  - Documentation 2.0 en transition (Developer Preview).

### Naomi

- Positionnement: assistant vocal OSS (heritage Jasper), orienté DIY.
- Points forts:
  - 100% open-source, philosophie maker.
- Vigilance:
  - Activite plus ancienne et ecosysteme plus restreint.

## 4) Recommandation pour AssistantVocal

Objectif declare: "assistant vocal facon Alexa" avec phases definition -> simulation -> prototype.

### Recommandation stack cible

1. Base coeur assistant:
   - Favoriser OpenVoiceOS comme socle evolutif principal.
2. Cible domotique:
   - S'integrer des le debut avec Home Assistant Assist pour les actions maison connectee.
3. Prototype rapide:
   - Garder le prototype CLI actuel (dans ce repo), puis brancher STT/TTS progressivement.
4. Options de secours:
   - S'inspirer de Rhasspy pour certains patterns offline (MQTT/intents), mais eviter de dependre d'un repo archive.

### Strategie pragmatique en 3 etapes

- Etape A (maintenant): simulation intents + scenarii de tests (deja demarre ici).
- Etape B: prototype vocal local (wake word + STT + TTS) avec architecture modulaire.
- Etape C: connecteurs domotiques et plugins (Home Assistant puis autres services).

## 7) Integration Leon dans ce repository

- Le projet inclut maintenant un fallback Leon dans la boucle de traitement des commandes.
- Pipeline actuel:
  - Intent reconnu localement: reponse locale immediate.
  - Intent inconnu: appel HTTP vers Leon.
  - Si Leon est indisponible: message de fallback explicite.
- Objectif: combiner robustesse locale (deterministe) + ouverture a des demandes plus libres via Leon.

## 5) Sources consultees

- OpenVoiceOS site: https://openvoiceos.org/
- OVOS core (GitHub): https://github.com/OpenVoiceOS/ovos-core
- Mycroft core (GitHub): https://github.com/MycroftAI/mycroft-core
- Rhasspy docs: https://rhasspy.readthedocs.io/en/latest/
- Rhasspy repo (GitHub): https://github.com/rhasspy/rhasspy
- Home Assistant Voice/Assist: https://www.home-assistant.io/voice_control/
- Home Assistant core (GitHub): https://github.com/home-assistant/core
- Leon site: https://getleon.ai/
- Leon repo (GitHub): https://github.com/leon-ai/leon
- Naomi repo (GitHub): https://github.com/NaomiProject/Naomi

## 6) Notes de fiabilite

- Ce comparatif est base sur informations publiques visibles a la date indiquee.
- Les statuts de maintenance peuvent evoluer vite: verifier les releases/issues avant engagement long terme.
