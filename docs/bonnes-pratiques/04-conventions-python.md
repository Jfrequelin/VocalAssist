# Conventions Python (projet AssistantVocal)

## Regles de base

- Suivre PEP 8 et utiliser des noms en `snake_case` pour fonctions et variables.
- Ajouter des annotations de type sur les fonctions publiques.
- Privilegier `pathlib`, `dataclasses` et la bibliotheque standard avant d'ajouter une dependance.
- Eviter les effets de bord dans les modules importes (pas de logique metier executee a l'import).

## Regles metier assistant vocal

- Isoler le parsing d'intention de la couche d'interface (CLI, puis voix).
- Garder une reponse deterministe pour un meme intent en mode simulation.
- Centraliser les intents et leurs reponses dans un module dedie.
- Versionner les scenarios de simulation pour eviter les regressions.

## Journalisation et observabilite

- Utiliser le module `logging` au lieu de `print` pour la production.
- Definir des niveaux de log coherents: DEBUG, INFO, WARNING, ERROR.
- Ne jamais logger de donnees sensibles (tokens, secrets, informations personnelles).
- Ajouter un identifiant de requete/session pour tracer les interactions utilisateur.
