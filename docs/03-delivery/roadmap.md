# Roadmap Produit

## Etat actuel

- Phase 1 (definition): terminee.
- Phase 2 (simulation): en place (scenarios + tests).
- Phase 3 (prototype vocal reel): en cours.

## Etapes suivantes

### Phase 0 — Bootstrap connectivité (prioritaire, bloquant tout le reste)

> Epic: [EDGE-phase0-bootstrap.md](epics/EDGE-phase0-bootstrap.md)

0a. Debug USB-C opérationnel (logs firmware visibles sur PC).  
0b. Provisioning WiFi via écran tactile (SSID + mot de passe, persisté en flash).  
0c. Ping HTTP base → serveur validé et affiché à l'écran.

**Rien d'autre ne démarre avant que ces trois points soient verts.**

### Phase 1 — Pipeline vocal (débute après Phase 0)

1. Stabiliser pipeline voix reel (capture, STT, TTS).
2. Renforcer fallback Leon (timeout, retry, circuit breaker).
3. Ajouter intents parametres (intent + slots + clarification).
4. Stabiliser streaming audio local edge.
5. Integrer actions Home Assistant critiques.

## Criteres de demo

- 0 crash sur scenarios de demo.
- intents critiques >= 95%.
- latence E2E mediane <= 1.8 s.
