# Securite, performance et Git

## Performance et securite

- Mesurer avant d'optimiser (pas d'optimisation prematuree).
- Valider toutes les entrees externes (utilisateur, API, fichiers).
- Proteger les secrets: ne jamais versionner de mots de passe ou tokens.

## Bonnes pratiques Git

- Faire des commits petits, coherents et clairement nommes.
- Ecrire des messages de commit explicites (quoi et pourquoi).
- Travailler avec des branches courtes et orientees fonctionnalite.

## Checklist avant merge

- Le code compile et les tests passent.
- Les nouveaux comportements sont testes.
- La documentation impactee est mise a jour.
- Aucun secret ni fichier temporaire n'est versionne.
