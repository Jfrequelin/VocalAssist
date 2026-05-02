# Changelog

Ce fichier conserve un historique synthétique des fonctionnalites implementees dans AssistantVocal.

Le format suit une structure simple inspiree de Keep a Changelog.

## [Unreleased]

### Added
- Base de packaging operable avec Docker Compose pour une demo reproductible.
- Runbook de deploiement/debug et smoke-test automatisable de la stack locale.
- Durcissement du backend edge sur les encodages audio/textes et la validation du proxy texte.
- Validation defensive de la configuration de capture audio.
- Tests cibles supplementaires sur edge audio, orchestrator et providers.
- Base de test firmware desktop avec peripheriques abstraits (micro, haut-parleur, ecran mock), harness d'echange assistant et script de lancement.
- Mode CLI principal `testbench` pour lancer la base de test firmware via `main.py`.
- Mode testbench etendu pour simuler une base complete sur Linux (transport local in-process, peripheriques systeme, commandes de controle runtime).
- Ecran Tk optionnel pour visualiser l'etat de la base Linux en temps reel dans le mode testbench.
- Indicateurs runtime du testbench (latence, intent/source, compteurs cumules) affiches en console et ecran.
- Export JSON optionnel du testbench avec resume de session et timeline horodatee des evenements.
- Backoff silence configurable dans le testbench (5 secondes par defaut apres `empty_audio`).

## [2026-05-02]

### Added
- Couches d'abstraction materiel modulaires cote firmware Rust, avec un fichier par peripherique dans le crate STM32.
- Format d'echange unifie firmware <-> assistant pour les types audio, texte, image, variable et binaire.
- Documentation d'architecture et tickets relies a l'abstraction firmware et au format d'echange unifie.
- Packaging local compose de assistant-backend, leon-mock et home-assistant-mock.
- Smoke-test de deploiement et runbook d'exploitation associe.

### Changed
- Le firmware edge converge vers un contrat canonique reutilisable par tous les peripheriques HAL.
- Le backend edge accepte explicitement les encodages texte et PCM16LE selon la configuration de compatibilite.
- Le fallback Leon ne compte plus une mauvaise configuration comme une panne ouvrant le circuit breaker.
- Le calcul du percentile P95 de latence vocale est aligne sur un arrondi superieur stable.

### Fixed
- Normalisation insensible a la casse du wake word cote edge.
- Rejet des frames PCM16LE de longueur impaire pour eviter les traitements invalides.
- Renforcement des tests de non-regression sur providers, capture audio et orchestrateur.

## [Historique initial]

### Added
- MVP local-first avec intents locaux, fallback Leon et pipeline vocal terminal/reel simulable.
- Activation vocale par wake word, gestion de session et messages systeme centralises.
- Providers externes pour lumiere, meteo et musique.
- Observabilite avec correlation IDs, logs structures et circuit breaker Leon.
- Synchronisation des tickets GitHub vers la base documentaire locale.

### Validated
- Base MVP consolidee et validee par la suite de tests documentee dans la documentation de statut produit.
