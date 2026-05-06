# Base ESP32-S3

Ce repertoire regroupe la documentation canonique de la base edge cible: Waveshare ESP32-S3-Touch-LCD-1.85C-BOX-EN.

## Objectif

Centraliser dans un seul endroit:
- le materiel cible et ses capacites;
- l'architecture firmware de la base;
- la configuration firmware separable du code metier;
- les peripheriques geres localement;
- les interfaces reseau avec le serveur.

## Materiel cible

Carte:
- ESP32-S3 dual-core LX7
- 16 MB Flash
- 8 MB PSRAM
- ecran rond 360x360
- tactile capacitif CST816S
- microphone + codec audio ES7210 / ES8311
- Wi-Fi 2.4 GHz + BLE

## Capacites exposees au serveur

La base doit annoncer a la connexion:
- audio_input
- audio_output
- display (presence, dimensions, format)
- touch
- camera
- encodages audio supportes
- encodages image supportes
- tailles max de chunks uplink/downlink

Reference protocole:
- ../../02-architecture/interfaces-and-contracts.md
- ../../02-architecture/schemas/protocol-v3-envelope.schema.json

## Code firmware associe

Repertoire source:
- ../../../src/base/firmware/esp32-s3/

Organisation cible du firmware:
- `src/main.rs`: point d'entree minimal
- `src/app.rs`: orchestration de l'application
- `src/config/`: constantes et configuration firmware
- `src/peripherals/`: helpers lies a la carte et au boot
- `src/audio/`, `src/lcd/`, `src/touch/`, `src/wifi/`, `src/server/`: drivers et services

## Sous-documents

- [Configuration firmware](firmware-configuration.md)
- [Peripheriques et board support](peripherals.md)
- [Firmware layout et execution](firmware-layout.md)
- [Reseau et protocole](network-and-protocol.md)
