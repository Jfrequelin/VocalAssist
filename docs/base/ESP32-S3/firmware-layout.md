# Firmware Layout ESP32-S3

## Vue d'ensemble

- `main.rs`: bootstrap Rust/ESP-IDF
- `app.rs`: sequence de boot, provisioning, boucle READY
- `config/`: configuration compile-time et board-specific
- `peripherals/`: helpers lies a la carte
- `audio/`: capture/lecture et codecs
- `lcd/`: driver LCD
- `touch/`: driver tactile
- `wifi/`: provisioning et connexion
- `server/`: HTTP/protocole serveur
- `buffers.rs`: buffers audio/video partages

## Regle de separation

## Code principal
- orchestration de haut niveau
- enchainement des etats
- decisions metier locales

## Code peripherique
- acces GPIO / I2C / SPI / I2S
- description des capacites de la carte
- comportement de boot lie au hardware

## Code configuration
- constantes, tailles, seuils, timeouts, pins, assets
