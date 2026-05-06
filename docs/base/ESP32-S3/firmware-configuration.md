# Configuration Firmware ESP32-S3

## Principe

La configuration firmware doit etre separee du code principal afin de:
- rendre explicites les constantes board-specific;
- limiter les regressions lors des changements hardware;
- faciliter les tests et le portage vers une autre revision de base.

## Categories de configuration

## Audio
- sample rate
- duree de capture
- gain playback
- seuils silence / VAD
- taille max de payload reseau

## Display
- largeur / hauteur LCD
- couleurs UI
- pins QSPI
- timing / reset / backlight

## Input
- GPIO bouton BOOT
- timings appui long
- I2C tactile

## Network
- timeout HTTP
- taille chunk audio/image
- heartbeat / retry / ack timeout

## Media
- asset audio de boot
- limites image/audio

## Convention de code

Configuration dans:
- `src/config/audio.rs`
- `src/config/display.rs`
- `src/config/input.rs`
- `src/config/network.rs`
- `src/config/media.rs`
- `src/config/mod.rs`

Le code applicatif ne doit pas dupliquer de constantes board-specific hors de `src/config/` sauf justification locale et commentee.
