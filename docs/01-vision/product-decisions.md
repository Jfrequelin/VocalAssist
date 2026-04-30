# Decisions Produit et Materiel

## Decisions actives

- DA-001: intelligence principale sur serveur local Leon.
- DA-002: wake word obligatoire sur edge.
- DA-003: commandes critiques executees localement sur edge.
- DA-004: lecture de flux audio executee localement sur edge.
- DA-005: commandes complexes et ouvertes delocalisees sur serveur.

## Materiel retenu v1

Edge:
- module ESP32-S3 avec haut-parleur integre.
- bouton mute materiel obligatoire.
- LED d'etat recommandee.

Serveur:
- machine Linux locale (mini PC/NUC ou equivalent).
- STT/TTS local + Leon.

## Risques et mitigations

- Qualite micro insuffisante:
  - mitigation: calibration, tests terrain, fallback push-to-talk.
- Wake word instable:
  - mitigation: seuils dynamiques et corpus bruit.
- Latence serveur:
  - mitigation: timeouts stricts, retries bornes, circuit breaker.
