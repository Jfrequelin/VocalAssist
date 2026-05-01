# Cadrage Produit

## Objectif

Construire un assistant vocal domestique type Alexa avec une architecture local-first:
- edge economique pour interaction temps reel,
- intelligence principale sur serveur local (Leon).

## Perimetre v1

Inclus:
- wake word local,
- commandes vocales basiques locales (stop, mute, volume, extinction/restart logique),
- routage vers serveur pour demandes complexes,
- commandes parametrees (intent + slots),
- lecture locale de TTS et flux audio.
- retour visuel local sur ecran pour les etats critiques (hardware disponible).
- interaction tactile locale minimale (hardware disponible).

Exclus:
- vision/camera,
- dependance cloud obligatoire,
- marketplace publique.

Non encore implemente dans ce depot (mais rendu possible par le hardware retenu):
- interface ecran/tactile complete,
- scenarios produits batterie/RTC/TF.

## Cibles qualite

- Intent critiques: >= 95% de succes.
- Corpus FR v1: >= 85%.
- Latence mediane E2E: <= 1.8 s.
- Fallback degrade propre: 100%.

## Personas

- Foyer domotique: commandes rapides maison.
- Productivite: rappels, agenda, contenu audio.
- Usage familial: commandes simples, mains libres.
