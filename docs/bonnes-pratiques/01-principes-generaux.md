# Principes generaux de codage

## Lisibilite

- Ecrire du code simple a lire, meme si ce n'est pas la version la plus "maligne".
- Utiliser des noms explicites pour les fonctions, variables et classes.
- Limiter la taille des fonctions: une fonction doit faire une seule chose.

## Structure et organisation

- Respecter une architecture claire (par domaine ou par fonctionnalite).
- Eviter les dependances circulaires entre modules.
- Separer clairement logique metier, I/O (fichier, reseau) et interface.

## Qualite du code

- Garder un style homogene (formatter et linter).
- Supprimer le code mort et les imports inutilises.
- Eviter la duplication: factoriser les blocs repetes.

## Gestion des erreurs

- Gerer les erreurs attendues avec des messages utiles.
- Ne jamais masquer une exception critique sans journalisation.
- Retourner des erreurs exploitables plutot que des messages vagues.
