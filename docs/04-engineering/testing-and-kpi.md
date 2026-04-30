# Strategie de Test et KPI

## Niveaux de test

- unitaires: intents, slots, routage.
- integration: edge <-> serveur <-> leon.
- e2e: commande vocale -> action -> reponse.
- terrain: bruit domestique, distance, coupures reseau.

## KPI techniques

- latence E2E (P50/P95)
- taux intents critiques
- taux global corpus FR
- taux faux positifs wake word
- taux fallback degrade propre
- stream start latency

## Validation minimum

- 10 commandes consecutives sans crash.
- commandes locales critiques repondent en < 300 ms.
- mode degrade fonctionne sans intervention manuelle.
