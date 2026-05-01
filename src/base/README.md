# Base ESP32-S3 - Fonctionnalites a implementer

Ce dossier regroupera le code execute sur la base edge ESP32-S3.

## Documentation materielle integree

- Datasheet ESP32-S3 integre: [src/base/ESP32_S3_DATASHEET_NOTES.md](src/base/ESP32_S3_DATASHEET_NOTES.md)
- Source PDF: https://files.waveshare.com/wiki/common/Esp32-s3_datasheet_en.pdf
- Wiki board constructeur: https://www.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.85
- Notes schema board integrees: [src/base/WAVESHARE_ESP32_S3_TOUCH_LCD_185_SCHEMATIC_NOTES.md](src/base/WAVESHARE_ESP32_S3_TOUCH_LCD_185_SCHEMATIC_NOTES.md)
- Datasheet DAC audio integre: [src/base/PCM5101PWR_DATASHEET_NOTES.md](src/base/PCM5101PWR_DATASHEET_NOTES.md)
- Source PDF DAC: https://files.waveshare.com/wiki/common/TexasInstruments-PCM5101PWR.pdf
- Index global datasheets composants: [src/base/COMPONENT_DATASHEETS_INDEX.md](src/base/COMPONENT_DATASHEETS_INDEX.md)
- Architecture logicielle base edge: [src/base/SOFTWARE_ARCHITECTURE.md](src/base/SOFTWARE_ARCHITECTURE.md)
- Build STM32 (cross-compile): [src/base/STM32_BUILD.md](src/base/STM32_BUILD.md)
- Build STM32 Rust: [src/base/RUST_STM32_BUILD.md](src/base/RUST_STM32_BUILD.md)

Synthese d'impact immediate issue du datasheet v1.6:
- Cible CPU/memoire: dual-core LX7 240 MHz, 384 KB ROM, 512 KB SRAM, 16 KB SRAM RTC
- Interfaces disponibles pour le firmware base: 2 I2S, 2 I2C, 3 UART, USB OTG, USB Serial/JTAG, 45 GPIO
- Securite hardware a prevoir dans la roadmap firmware: Secure Boot, Flash Encryption, AES/SHA/RSA/HMAC
- Vigilance hardware: VDD_SPI et variantes (notamment S3R8V avec GPIO47/48 en 1.8 V)
- Contraintes operationnelles wiki: sequences BOOT/RESET pour recovery flash, vigilance memoire audio+BLE, adresses I2C onboard (`0x15`, `0x20`, `0x51`)
- Contraintes schema: blocs audio (PCM5101 + ampli), RTC (PCF85063), IMU (QMI8658), bus LCD/touch et lignes BAT/USB a prendre en compte dans l'ordre d'initialisation firmware
- Contraintes DAC PCM5101: I2S 3 fils (LRCK/BCK/DIN), mute pop-free, gestion clock-halt, sequence power/clock stricte

## Objectif

Fournir une base edge robuste qui:
- capte l'audio localement,
- detecte le wake word,
- envoie les requetes au backend,
- joue les reponses TTS,
- reste operationnelle en mode degrade.

## Perimetre MVP (obligatoire)

### 1. Audio et activation locale
- Capture micro 16 kHz mono PCM
- Wake word local configurable (defaut: nova)
- VAD minimal pour filtrer le bruit
- Commandes locales de base: stop, mute, volume
- Implementation calibree pour contrainte memoire/CPU ESP32-S3 (buffers limites, zero fuite)

### 2. Communication reseau
- Client HTTP vers endpoint backend `/edge/audio`
- Correlation ID sur chaque requete
- Retry + backoff exponentiel
- Timeout strict et gestion d'erreurs claire
- Budget latence compatible 2.4 GHz Wi-Fi et mode degrade local si perte reseau

### 3. Restitution et etat appareil
- Lecture locale TTS (wav/pcm)
- Gestion etats edge: idle, listening, sending, speaking, error, muted
- Bouton physique mute prioritaire
- LED etat minimale

### 4. Robustesse
- Mode degrade si backend indisponible
- Reconnexion automatique sans reboot manuel
- Journalisation minimale (UART et/ou stockage local)
- Pas de crash sur boucle de tests repetes
- Conception prete pour phases low-power (PMU/ULP) sans regression fonctionnelle

## Perimetre V1+ (apres MVP)

### 5. UI locale
- Affichage ecran des etats runtime
- Retour visuel sur erreur/reconnexion
- Commandes tactiles minimales (mute, stop, validation)

### 6. Capacites hardware avancees
- Gestion batterie (niveau, charge, alertes)
- Usage RTC (horodatage, reprise)
- Usage TF (logs persistants, cache local)

## Exclusions (hors scope base edge)
- NLU complexe
- Orchestration metier
- Memoire conversationnelle long terme
- Dependances cloud obligatoires

## Definition de Done (MVP)

- Capture audio stable >= 10 min sans fuite visible
- Wake word detecte de facon fiable en environnement domestique
- Roundtrip edge -> backend -> TTS acceptable (P95 cible <= 2.5s)
- Reprise reseau automatique validee
- Tests unitaires edge critiques verts
- Documentation technique deploiement + diagnostic disponible

## Structure logicielle actuellement en place

- `src/base/config.py`: configuration runtime edge (device, serveur, retries, timeouts)
- `src/base/contracts.py`: contrats reseau (`EdgeAudioRequest`, `EdgeAudioResponse`)
- `src/base/state_machine.py`: machine a etats edge (idle/listening/sending/speaking/muted/error)
- `src/base/transport.py`: client HTTP resilient pour `POST /edge/audio`
- `src/base/runtime.py`: orchestration du flux local -> serveur assistant
- `src/base/interfaces.py`: interfaces injectables pour transport/playback
- `src/base/SOFTWARE_ARCHITECTURE.md`: description globale des flux et responsabilites

## Cible embarquee STM32

### Option C (legacy)
- `src/base/firmware/stm32/include/base_runtime.h`: API C portable du coeur runtime
- `src/base/firmware/stm32/src/base_runtime.c`: implementation C sans dependance OS
- `src/base/firmware/stm32/CMakeLists.txt`: build CMake (host + stm32)
- `src/base/firmware/stm32/cmake/toolchain-stm32-gcc.cmake`: toolchain ARM GCC

### Option Rust (recommandée)
- `src/base/firmware/stm32-rust/src/lib.rs`: runtime portable + couverture tests
- `src/base/firmware/stm32-rust/examples/main.rs`: exemple d'utilisation
- `src/base/firmware/stm32-rust/Cargo.toml`: configuration Cargo (host + cross-compile)
- `src/base/firmware/stm32-rust/tests/`: tests d'intégration
- Avantages: sécurité mémoire, gestion automatique ressources, zéro overhead runtime

## Structure de code cible (prochaine etape hardware)

- `audio_capture.py`: capture micro + buffer I2S
- `wakeword.py`: detection wake word embarquee
- `vad.py`: filtrage activite vocale
- `playback.py`: sortie audio locale DAC/amp
- `device_state.py`: integration LED/ecran/tactile sur state machine
- `resilience.py`: mode degrade, watchdog, reprise reseau

## Priorisation implementation

1. Audio capture + wake word + transport HTTP
2. TTS playback + state machine de base
3. Retry/backoff + mode degrade
4. Ecran/tactile
5. Batterie/RTC/TF
