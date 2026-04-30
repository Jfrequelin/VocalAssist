# Plan d'execution 2 semaines - AssistantVocal (Edge + Leon)

> Legacy: document conserve pour historique.
> Source canonique: `docs/03-delivery/sprint-2-weeks.md`.

Date: 2026-04-30
Perimetre: voix et commandes vocales uniquement
Objectif: passer du prototype actuel a un MVP technique stabilise

Hypothese materielle:
- Edge V1 base sur module ESP32-S3 avec haut-parleur integre.
- Serveur local responsable de STT/NLU/TTS avance et Leon.

## 1. Objectifs de sprint (14 jours)

- Mettre en place un pipeline vocal reel minimal (capture audio + STT + TTS).
- Renforcer le fallback Leon (timeout, retry, circuit breaker, observabilite).
- Valider 30 commandes FR (fixes + ouvertes) avec un taux de succes cible.
- Produire un socle de tests et KPI pour piloter la suite.

## 2. Definition de done (global)

- Tous les tickets P1 sont termines.
- Tests unitaires/integration passent en CI locale.
- Scenarios de demo executes sans crash.
- KPI minimaux mesures et documentes.

## 3. Backlog priorise

## P1 - Critique (semaine 1)

### EDGE-01 - Capture audio reel

Description:
- Ajouter un module de capture micro (16 kHz mono PCM) avec buffer circulaire.

Acceptance criteria:
- Lecture micro stable pendant 10 minutes sans fuite memoire visible.
- Fichier WAV de test exportable.

Estimation: 1.0 j

### EDGE-02 - VAD local

Description:
- Integrer VAD pour detecter debut/fin de parole et limiter le bruit.

Acceptance criteria:
- Segmentation parole correcte sur 20 essais en environnement calme.
- Eviter l'envoi de silence au STT.

Estimation: 1.0 j

### SRV-01 - STT local serveur (faster-whisper)

Description:
- Ajouter un endpoint STT sur serveur central pour transcrire l'audio edge.

Acceptance criteria:
- Reponse JSON avec texte + confidence + latence.
- 85%+ de transcription correcte sur corpus FR interne de base.

Estimation: 1.5 j

### SRV-02 - TTS local serveur (Piper)

Description:
- Ajouter un endpoint TTS retournant audio PCM/WAV.

Acceptance criteria:
- Synthese stable sur 30 phrases FR.
- Latence moyenne acceptable (< 800 ms sur phrases courtes).

Estimation: 1.0 j

### ORCH-01 - Hardening fallback Leon

Description:
- Ajouter retry borne + timeout strict + circuit breaker dans le client Leon.

Acceptance criteria:
- Aucun blocage complet si Leon indisponible.
- Bascule degradee en moins de 2.5 s.

Estimation: 1.0 j

### OBS-01 - Correlation ID et logs structures

Description:
- Ajouter correlation_id par interaction, logs structures edge et serveur.

Acceptance criteria:
- Trace complete visible sur 10 interactions consecutives.

Estimation: 0.5 j

## P2 - Important (semaine 2)

### EDGE-03 - Wake word reel

Description:
- Brancher un moteur wake word local (placeholder + calibration).

Acceptance criteria:
- Detection correcte sur 50 essais en calme.
- Faux positifs limites sur 30 min de bruit TV faible.

Estimation: 1.5 j

### ORCH-02 - Politique de routage voix

Description:
- Router local d'abord pour intents critiques, serveur sinon.

Acceptance criteria:
- stop/mute/annule traites localement a 100%.
- intents inconnus routent serveur + fallback propre.

Estimation: 1.0 j

### DOM-01 - Actions Home Assistant minimales

Description:
- Integrer 3 actions: lumiere on/off, etat temperature, scene simple.

Acceptance criteria:
- 10 executions de chaque action sans erreur critique.

Estimation: 1.0 j

### QA-01 - Corpus FR et scenarios E2E

Description:
- Construire jeu de tests FR (30 commandes) nominal + bruit modere.

Acceptance criteria:
- Test runner produit taux de succes par categorie.

Estimation: 1.0 j

### QA-02 - Tests reseau degrade

Description:
- Simuler perte serveur et verifier mode degrade edge.

Acceptance criteria:
- Message utilisateur clair et aucun crash.
- Recuperation automatique apres retour reseau.

Estimation: 0.5 j

### DOC-01 - Runbook installation + debug

Description:
- Documenter setup edge, setup serveur, check-list debug.

Acceptance criteria:
- Un nouvel environnement peut lancer la demo en <= 45 min.

Estimation: 0.5 j

## P3 - Nice to have

- Multi-utilisateur vocal (profils)
- Optimisation latence TTS
- Dashboard simple de KPI

## 4. Planning journalier propose

## Semaine 1

Jour 1:
- EDGE-01
- OBS-01

Jour 2:
- EDGE-02
- SRV-01 (demarrage)

Jour 3:
- SRV-01 (fin)
- SRV-02

Jour 4:
- ORCH-01
- tests unitaires associes

Jour 5:
- Integration edge <-> stt/tts
- revue KPI intermediaire

## Semaine 2

Jour 6:
- EDGE-03 (demarrage calibration)

Jour 7:
- EDGE-03 (fin)
- ORCH-02

Jour 8:
- DOM-01

Jour 9:
- QA-01
- QA-02

Jour 10:
- DOC-01
- campagne finale + go/no-go

## 5. KPI cibles fin de sprint

- Latence E2E mediane <= 1.8 s
- Taux intents critiques reussis >= 95%
- Taux commandes FR global >= 85%
- Crash runtime: 0 sur campagne finale
- Taux fallback degrade propre: 100%

## 6. Risques et plans de mitigation

Risque: STT trop lent
- Mitigation: modele plus petit, batching des buffers, optimisation CPU.

Risque: wake word instable
- Mitigation: calibration micro, seuil dynamique, corpus bruit.

Risque: endpoint Leon non compatible
- Mitigation: adaptateur de schema et tests d'integration contractuelle.

Risque: materiel micro insuffisant
- Mitigation: bascule temporaire sur micro USB reference pour baseline.

## 7. Demo de fin de sprint

Script de demo:
1. "Nova, quelle heure est-il"
2. "Nova, allume la lumiere du salon"
3. "Nova, rappelle-moi de sortir les poubelles demain"
4. "Nova, explique-moi rapidement la theorie des cordes"
5. Coupure serveur simulee
6. "Nova, stop"

Criteres demo:
- Aucun crash
- Reponses vocales coherentes
- Bascule degradee visible et propre
