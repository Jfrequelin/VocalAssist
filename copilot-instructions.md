# Copilot Instructions - AssistantVocal

Ces instructions guident GitHub Copilot pour ce repository.

## Contexte projet

- Projet Python d'assistant vocal type Alexa.
- Priorite actuelle: definition, simulation, puis prototype local.
- Structure de reference:
  - `main.py`
  - `src/assistant/`
  - `docs/`

## Documentation de reference

- [README.md](README.md)
- [docs/README.md](docs/README.md)
- [docs/01-vision/product-definition.md](docs/01-vision/product-definition.md)
- [docs/01-vision/product-decisions.md](docs/01-vision/product-decisions.md)
- [docs/02-architecture/system-architecture.md](docs/02-architecture/system-architecture.md)
- [docs/02-architecture/interfaces-and-contracts.md](docs/02-architecture/interfaces-and-contracts.md)
- [docs/03-delivery/roadmap.md](docs/03-delivery/roadmap.md)
- [docs/03-delivery/sprint-2-weeks.md](docs/03-delivery/sprint-2-weeks.md)
- [docs/04-engineering/coding-guidelines.md](docs/04-engineering/coding-guidelines.md)
- [docs/04-engineering/testing-and-kpi.md](docs/04-engineering/testing-and-kpi.md)
- [docs/05-research/assistant-benchmark.md](docs/05-research/assistant-benchmark.md)
- [docs/bonnes-pratiques-codage.md](docs/bonnes-pratiques-codage.md)
- [docs/bonnes-pratiques/01-principes-generaux.md](docs/bonnes-pratiques/01-principes-generaux.md)
- [docs/bonnes-pratiques/02-tests-et-documentation.md](docs/bonnes-pratiques/02-tests-et-documentation.md)
- [docs/bonnes-pratiques/03-securite-et-git.md](docs/bonnes-pratiques/03-securite-et-git.md)
- [docs/bonnes-pratiques/04-conventions-python.md](docs/bonnes-pratiques/04-conventions-python.md)
- [docs/bonnes-pratiques/05-definition-of-done.md](docs/bonnes-pratiques/05-definition-of-done.md)
- [docs/99-legacy/README.md](docs/99-legacy/README.md)

## Regles de code

- Respecter les conventions de [docs/bonnes-pratiques-codage.md](docs/bonnes-pratiques-codage.md).
- Garder les fonctions courtes et a responsabilite unique.
- Ajouter des types sur les fonctions publiques et des noms explicites.
- Eviter les changements de style non necessaires hors du scope.

## Regles metier assistant vocal

- Separer clairement le parsing d'intentions de la couche interface.
- Ajouter les nouveaux intents dans un module centralise.
- Conserver un comportement deterministe en mode simulation.
- Ne jamais casser les commandes existantes sans mise a jour des scenarios.

## Qualite et validation

- Proposer des tests pour toute nouvelle logique metier.
- Verifier qu'un lancement local fonctionne apres modification.
- Mettre a jour la documentation lorsque le comportement change.

## Securite

- Ne jamais introduire de secrets en dur dans le code.
- Valider et normaliser les entrees externes.
- Eviter de logger des donnees sensibles.
