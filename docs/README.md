# Documentation AssistantVocal

Cette documentation est organisee par domaines pour faciliter la lecture et l'execution.

Plateforme cible edge: **ESP32-S3** (Waveshare ESP32-S3-Touch-LCD-1.85C-BOX-EN).

## Statut courant (Mai 2026)

- [Statut MVP consolide](MVP_STATUS.md)
- [Cycle de session conversationnel](SESSION_CYCLE.md)

## 1. Vision produit

- [Cadrage produit](01-vision/product-definition.md)
- [Decisions produit et materiel](01-vision/product-decisions.md)

## 2. Architecture technique

- [Architecture edge + serveur](02-architecture/system-architecture.md)
- [Interfaces et contrats API](02-architecture/interfaces-and-contracts.md)
- [Mode degrade et reconnexion edge](02-architecture/edge-reconnect-degraded-mode.md)

## 3. Livraison et pilotage

- [Roadmap produit](03-delivery/roadmap.md)
- [Plan d'execution 2 semaines](03-delivery/sprint-2-weeks.md)
- [Epics](03-delivery/epics/README.md)

## 4. Engineering

- [Standards de code](04-engineering/coding-guidelines.md)
- [Strategie de test et KPI](04-engineering/testing-and-kpi.md)
- [Base de test firmware](04-engineering/testing-base-firmware.md)
- [Tests terrain edge](04-engineering/field-tests/edge-field-test-matrix.md)
- [Checklist terrain edge](04-engineering/field-tests/edge-field-checklist.md)

## 5. Recherche et benchmark

- [Comparatif des assistants vocaux](05-research/assistant-benchmark.md)
- [Schema materiel Waveshare ESP32-S3-Touch-LCD-1.85C (PDF)](05-research/hardware/ESP32-S3-Touch-LCD-1.85C_V2.pdf)
- [Wiring hardware ESP32-S3-Touch-LCD-1.85C](05-research/hardware/wiring.md)

## Legacy

Les anciens documents (historique proto V1, anciens plans) sont conserves dans `docs/99-legacy/`.
