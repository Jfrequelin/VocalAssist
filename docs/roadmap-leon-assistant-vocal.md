# Roadmap Leon pour un assistant vocal complet

> Legacy: document conserve pour historique.
> Sources canoniques:
> - `docs/03-delivery/roadmap.md`
> - `docs/03-delivery/sprint-2-weeks.md`

Date de reference: 2026-04-30
Horizon: 6 mois
Moteur principal: Leon

Plan court terme associe:
- docs/plan-execution-2-semaines.md

## 1. Vision produit

Construire un assistant vocal de niveau production, type Alexa-like, base sur Leon comme cerveau principal.

Objectifs:
- Commandes vocales naturelles en francais.
- Domotique fiable avec Home Assistant.
- Fonctionnement local-first avec fallback cloud optionnel.
- Architecture modulaire, testable, et deployable sur mini PC ou Raspberry Pi.

## 2. Resultats attendus (definition of success)

A 6 mois, le systeme doit:
- Repondre a 95% des commandes critiques sans crash.
- Atteindre une latence mediane inferieure a 1.5 s en local.
- Atteindre un taux de wake-word correct superieur a 97% en environnement domestique.
- Atteindre un taux de reconnaissance intention correcte superieur a 90% sur jeu de test versionne.
- Fournir observabilite complete: logs, traces de bout en bout, metriques audio et intention.

## 3. Architecture cible

Pipeline global:
1. Wake word et VAD
2. Capture audio et pre-traitement
3. STT local
4. Orchestration intents locales
5. Fallback Leon pour demandes ouvertes
6. Actions domotiques via Home Assistant
7. TTS local
8. Monitoring, audit, et gestion erreurs

Composants:
- Couche audio: micro, suppression bruit, VAD, wake word
- Couche interpretation: intents deterministes + Leon
- Couche action: services metier et domotique
- Couche dialogue: gestion contexte court terme et confirmations
- Couche plateforme: logs, metrics, config, mise a jour

## 4. Phases de livraison

## Phase 0 - Cadrage technique (S1-S2)

Livrables:
- ADR architecture Leon + pipeline voix
- Choix moteurs: wake word, STT, TTS, VAD
- Definition du contrat API Leon utilise par le projet
- Plan de tests et KPI techniques

Critere de sortie:
- Stack finale validee
- Environnement dev reproductible

## Phase 1 - Socle vocal local (S3-S6)

Livrables:
- Wake word local operationnel
- STT local branche sur pipeline
- TTS local branche sur pipeline
- Gestion erreur micro et reprise automatique

Critere de sortie:
- Conversation basique hands-free operationnelle
- 20 commandes vocales executees consecutivement sans crash

## Phase 2 - Intelligence hybride avec Leon (S7-S10)

Livrables:
- Orchestrateur local plus fallback Leon robuste
- Timeouts, retries, et circuit breaker sur appels Leon
- Context window conversationnelle courte
- Politique de priorite local puis Leon puis message degrade

Critere de sortie:
- Tous intents critiques traites localement
- Intent inconnu gere par Leon ou degrade propre

## Phase 3 - Domotique et routines (S11-S14)

Livrables:
- Connecteur Home Assistant stable
- Routines: matin, nuit, absence, cinema
- Confirmation vocale pour actions sensibles
- Gestion des permissions par type d action

Critere de sortie:
- 15 scenarios maison automatises valides
- Zero action sensible executee sans confirmation

## Phase 4 - Qualite, securite, observabilite (S15-S18)

Livrables:
- Dashboard de metriques (latence, erreurs, wake accuracy)
- Traces pipeline audio->intent->action->tts
- Politique logs et retention
- Tests de charge conversationnelle et endurance

Critere de sortie:
- MTBF acceptable pour usage quotidien
- Procedure de diagnostic claire en cas incident

## Phase 5 - Beta utilisateur et industrialisation (S19-S24)

Livrables:
- Programme beta en conditions reelles
- Packaging deployment one-command
- Guide exploitation et runbook
- Plan maintenance trimestriel

Critere de sortie:
- Satisfaction beta >= 4/5
- Taux succes commandes critiques >= 95%

## 5. Backlog prioritaire

P1:
- Wake word fiable en bruit ambiant
- STT francais local performant
- Fallback Leon stable
- Integrations Home Assistant critiques

P2:
- Multi-room et satellites
- Multi-utilisateur et profils
- Personnalite vocale et style reponse

P3:
- Edge AI avance
- Marketplace de skills internes
- Analytics produit avancees

## 6. Strategie de test

Niveaux de test:
- Unitaires: intents, routeur, connecteurs
- Integration: pipeline voix complet
- E2E: scenario utilisateur de bout en bout
- Terrain: tests maison reels avec bruit

Jeux de test:
- Corpus commande nominale
- Corpus ambigu et accents
- Corpus environnement bruyant

Cadence:
- CI sur chaque merge
- Campagne audio hebdo
- Revue KPI hebdomadaire

## 7. Securite et vie privee

Principes:
- Local-first par defaut
- Chiffrement des secrets et rotation
- Donnees minimales, retention limitee
- Journalisation sans contenu sensible

Controles:
- Auth API locale pour actions critiques
- Liste blanche commandes sensibles
- Validation explicite avant action irreversible

## 8. Risques et mitigations

Risque: latence trop elevee
Mitigation: cache, optimisation audio, fallback local deterministe

Risque: faux positifs wake word
Mitigation: calibration, double seuil, tests multi-conditions

Risque: indisponibilite Leon
Mitigation: mode degrade local, circuit breaker, message utilisateur clair

Risque: fragmentation materielle
Mitigation: matrice hardware supportee et profils config

## 9. Planning hebdomadaire type

Chaque semaine:
- Lundi: objectifs et plan
- Mardi-Mercredi: implementation
- Jeudi: validation technique et tests audio
- Vendredi: revue KPI et decisions

## 10. Prochaines actions immediates (2 semaines)

Semaine 1:
- Valider endpoint Leon final et schema payload/reponse
- Integrer timeouts/retries/circuit breaker dans le client Leon
- Ajouter tests integration pour fallback reseau

Semaine 2:
- Brancher premier moteur STT local reel
- Brancher premier moteur TTS local reel
- Mesurer latence STT->TTS sur 30 commandes

## 11. Iteration suivante (semaines 3-4)

Contexte:
- Edge V1 retenu: module ESP32-S3 avec haut-parleur integre.
- Intelligence avancee maintenue sur serveur local (Leon + services voix).

### Axe A - Commandes parametrees (intent + slots)

Objectif:
- Supporter des commandes du type: "joue le podcast XXXX depuis France Inter".

Livrables:
- Schema d'intents parametres (intent, slots obligatoires, slots optionnels).
- Extracteur de slots FR (nom podcast, source, episode, date, position).
- Mecanisme de clarification vocale si slots incomplets ou ambigus.
- Politique de resolution des sources (provider prioritaire puis fallback).

Criteres de sortie:
- 20 commandes parametrees executees avec >= 85% de succes.
- Clarification reussie sur au moins 90% des cas ambigus du corpus.

### Axe B - Lecture de flux audio locale edge

Objectif:
- Le serveur envoie des ordres de lecture, l'edge joue localement les flux.

Livrables:
- Commande `play_stream` stabilisee (contrat v1).
- Buffer local edge + retry borne + arret propre sur perte reseau.
- Commandes locales actives pendant lecture: stop, pause, resume, volume.

Criteres de sortie:
- Demarrage lecture flux < 1.2 s mediane.
- Arret/pause/reprise local en < 300 ms.
- 0 crash sur campagne streaming de 60 min.

### Axe C - Robustesse operationnelle

Livrables:
- Circuit breaker valide en conditions reseau degradees.
- Logs structures avec correlation_id de bout en bout.
- Rapport KPI hebdomadaire standardise.

Criteres de sortie:
- Taux fallback degrade propre = 100% sur tests de coupure serveur.
- Traces completement corrigees sur 15 scenarios E2E.
