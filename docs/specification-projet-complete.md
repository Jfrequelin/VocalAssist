# Specification complete du projet AssistantVocal

> Legacy: document conserve pour historique.
> Sources canoniques:
> - `docs/01-vision/product-definition.md`
> - `docs/01-vision/product-decisions.md`
> - `docs/02-architecture/system-architecture.md`
> - `docs/02-architecture/interfaces-and-contracts.md`

Date: 2026-04-30
Version: v1.0 (cadre de reference)
Statut: baseline de conception

## 1. Resume executif

AssistantVocal est un assistant vocal domestique de type Alexa-like avec intelligence principale centralisee sur un serveur local (Leon), et peripheriques edge economiques (ESP32-S3) pour l'interaction temps reel.

Objectif principal:
- Offrir une experience vocale fiable, locale-first, avec commandes basiques traitees en local edge et commandes complexes traitees par le serveur.

## 2. Perimetre produit

Inclus:
- Wake word local sur edge.
- Commandes systeme locales critiques.
- Envoi audio edge vers serveur local.
- STT, orchestration, NLU et generation centralises serveur.
- Lecture locale edge de TTS et flux audio.
- Integrations domotiques de base via Home Assistant.

Exclus (v1):
- Vision / camera.
- Cloud obligatoire.
- Marketplace de skills publique.

## 3. Objectifs mesurables

- Disponibilite commande critique locale: >= 99%.
- Latence mediane commande vocale E2E: <= 1.8 s (v1).
- Taux de succes intents critiques: >= 95%.
- Taux de succes global corpus FR v1: >= 85%.
- Taux de fallback degrade propre: 100% en cas d'indisponibilite serveur.

## 4. Personas et usages cibles

Personas:
- Utilisateur foyer: commandes rapides maison connectee.
- Utilisateur productivite: rappels, agenda, podcasts.
- Utilisateur familial: usage simple, mains libres.

Usages prioritaires:
- Commandes systeme locales: stop, mute, volume, extinction.
- Domotique: lumiere, scene, etat temperature.
- Contenu audio: podcasts, radios, flux.
- Questions ouvertes via Leon.

## 5. Architecture systeme (vue globale)

Topologie:
- Edge(s): satellites vocaux ESP32-S3.
- Serveur local: Leon + services voix + orchestration + integrations.

Principe de routage:
1. Edge detecte wake word.
2. Edge traite commandes critiques locales en priorite.
3. Si commande non locale, edge envoie audio/texte au serveur.
4. Serveur retourne reponse, actions et ordres de lecture.
5. Edge lit localement le son et execute les controles locaux.

## 6. Definition des sous-systemes

## 6.1 Sous-systeme Edge

Responsabilites:
- Wake word local obligatoire.
- VAD et capture audio.
- Pre-traitement audio (gain, filtrage simple).
- Commandes locales critiques:
  - stop
  - mute micro
  - annule
  - volume plus/moins
  - extinction logique appareil
  - redemarrage logique appareil
- Lecture locale TTS et streaming.
- Signalisation locale (LED/bouton).

Contraintes:
- Faible conso.
- Tolerance aux coupures reseau.
- Reponse locale commandes critiques < 300 ms.

## 6.2 Sous-systeme Serveur local

Responsabilites:
- STT serveur (francais).
- Orchestrateur intents locales + fallback Leon.
- NLU pour commandes parametrees (intent + slots).
- Gestion clarifications en cas ambiguite.
- Integrations Home Assistant / APIs externes.
- TTS serveur.
- Monitoring, logs, KPI.

Contraintes:
- Requetes concurrentes multi-edge.
- Timeouts stricts, retries bornes, circuit breaker.
- Journalisation structuree et securisee.

## 7. Materiel de reference

## 7.1 Edge V1 (choix retenu)

- Module ESP32-S3 avec haut-parleur integre.
- Micro (integre ou externe selon module final).
- Bouton mute materiel prioritaire.
- LED etat (ecoute, traitement, erreur).
- Alimentation 5V stable.

## 7.2 Serveur local

- Mini PC x86 ou machine Linux locale.
- Ressources dimensionnees pour STT/TTS + Leon.
- Stockage SSD.
- Reseau local stable (Ethernet recommande).

## 8. Logiciels et stack technique

Edge:
- Firmware ESP32-S3.
- Wake word engine embarque.
- Capture audio + VAD.
- Client transport vers serveur.
- Player audio local.

Serveur:
- Runtime Python pour orchestrateur.
- Leon comme moteur intelligence principal.
- STT local (faster-whisper ou equivalent).
- TTS local (Piper ou equivalent).
- Connecteur Home Assistant.

## 9. Interfaces et contrats

## 9.1 Interface Edge -> Serveur (commande vocale)

Modele logique:
- device_id
- session_id
- correlation_id
- audio ou texte transcrit
- metadata (langue, confidence, contexte)

## 9.2 Interface Serveur -> Edge (reponse)

Modele logique:
- answer_text
- intent
- source (local/leon/degrade)
- action optionnelle
- policy (cache, retry, confirmation)

## 9.3 Interface streaming audio (ordre serveur)

Action type:
- play_stream(url, codec, buffer_ms, retry_policy)

Controles edge locaux obligatoires en lecture:
- stop
- pause
- resume
- volume +/ -

## 9.4 Interface commandes parametrees (intent + slots)

Exemple:
- intent: play_podcast
- slots obligatoires: podcast_name, provider
- slots optionnels: episode_name, date, position

Statuts:
- ready_to_execute
- needs_clarification
- not_found

## 10. Strategie de routage fonctionnel

Priorite d'execution:
1. Commandes critiques locales edge.
2. Intents deterministes locales.
3. Fallback serveur Leon pour demandes ouvertes/complexes.
4. Mode degrade local si serveur indisponible.

## 11. Securite et vie privee

- Local-first par defaut.
- TLS sur liens edge-serveur.
- Auth device/serveur (token ou certificat).
- RBAC simplifie pour actions sensibles.
- Minimisation des donnees.
- Pas de logs audio brut par defaut.
- Retention courte des transcriptions.

## 12. Observabilite

Metriques minimales:
- Latence E2E (P50/P95).
- Wake word success/faux positifs.
- Taux intents corrects.
- Taux fallback degrade.
- Stream start latency.
- Coupures lecture/heure.

Tracabilite:
- correlation_id unique par interaction.
- trace pipeline complete.

## 13. Modes de fonctionnement

- Mode normal: edge + serveur.
- Mode degrade: edge local uniquement.
- Mode maintenance: actions sensibles bloquees.

## 14. Tests et validation

Niveaux:
- Unitaires (intent/slots/routage).
- Integration (edge-serveur).
- E2E (voix -> action -> reponse).
- Terrain (bruit domestique, distance, coupure reseau).

Go/No-Go materiel edge:
- Wake word valide en calme et bruit modere.
- Commandes locales < 300 ms.
- Streaming stable 60 min sans crash.

## 15. Plan de livraison

Phase A (2 semaines):
- Pipeline vocal minimal reel.
- Hardening fallback Leon.
- KPI de base.

Phase B (2 semaines):
- Commandes parametrees (intent + slots).
- Clarifications vocales.
- Lecture streaming locale stabilisee.

Phase C (4+ semaines):
- Integrations domotiques et routines.
- Durcissement securite et observabilite.
- Preparation beta terrain.

## 16. Risques principaux

- Instabilite wake word edge en bruit.
- Latence STT trop elevee.
- Incompatibilites endpoint Leon.
- Qualite micro module variable.

Mitigations:
- calibration wake word + mode push-to-talk de secours,
- profils de performance STT,
- tests contractuels API,
- qualification hardware par checklist.

## 17. Decisions d'architecture actives

- DA-001: intelligence principale sur serveur local Leon.
- DA-002: wake word et commandes critiques obligatoirement locales edge.
- DA-003: lecture de flux audio en local edge sur ordre serveur.
- DA-004: commandes parametrees gerees par schema intent + slots avec clarification.

## 18. Definitions (glossaire)

- Edge: peripherique vocal local (satellite).
- Serveur local: noeud central intelligence et orchestration.
- Intent: intention utilisateur detectee.
- Slot: parametre extrait d'une commande.
- Fallback: mecanisme de secours vers niveau suivant.
- Mode degrade: fonctionnement limite en cas de panne partielle.
