# Decisions Produit et Materiel

## Decisions actives

- DA-001: intelligence principale sur serveur local Leon.
- DA-002: wake word obligatoire sur edge.
- DA-003: commandes critiques executees localement sur edge.
- DA-004: lecture de flux audio executee localement sur edge.
- DA-005: commandes complexes et ouvertes delocalisees sur serveur.

## Materiel retenu v1

Edge:
- module cible: Waveshare ESP32-S3-Touch-LCD-1.85C-BOX-EN.
- ecran LCD tactile 1.85" (360x360) disponible pour HMI locale.
- audio embarque (micro + sortie haut-parleur) pour capture et restitution locales.
- bouton mute materiel obligatoire.
- LED d'etat recommandee.
- batterie rechargeable, RTC et slot TF disponibles pour evolutions produit.

## Fonctionnalites accessibles avec le hardware retenu

Disponibles materiellement:
- affichage local des etats edge (idle, listening, thinking, speaking, error, muted),
- interaction tactile minimale (mute/stop/navigation simple),
- capture vocale locale,
- restitution audio locale,
- connectivite Wi-Fi/BLE,
- fonctionnement sur batterie,
- horodatage local via RTC,
- stockage auxiliaire via TF.

Disponibles dans le depot actuel (simulation/proto):
- wake word local,
- VAD minimal,
- envoi audio edge vers backend,
- restitution TTS locale,
- etats LED/mute/bouton,
- mode degrade + reconnexion simple.

Non encore integrees dans ce depot:
- pipeline ecran/tactile complet,
- gestion produit batterie/RTC/TF.

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
