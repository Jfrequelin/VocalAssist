# ESP32-S3 Datasheet Integration Notes

Source integree:
- Espressif ESP32-S3 Series Datasheet v1.6
- URL: https://files.waveshare.com/wiki/common/Esp32-s3_datasheet_en.pdf
- Waveshare wiki ESP32-S3-Touch-LCD-1.85
- URL: https://www.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.85
- Waveshare schematic ESP32-S3-Touch-LCD-1.85
- URL: https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.85/ESP32-S3-Touch-LCD-1.85.pdf

Notes de cablage et composants extraites du schema:
- [src/base/WAVESHARE_ESP32_S3_TOUCH_LCD_185_SCHEMATIC_NOTES.md](src/base/WAVESHARE_ESP32_S3_TOUCH_LCD_185_SCHEMATIC_NOTES.md)

Objectif:
- traduire les caracteristiques du datasheet en exigences concretes pour le code base edge.

## 1) Capacites SoC a retenir pour la base edge

- CPU: Xtensa dual-core 32-bit LX7, jusqu'a 240 MHz
- Memoire integree:
  - 384 KB ROM
  - 512 KB SRAM
  - 16 KB SRAM RTC
- Radio:
  - Wi-Fi 2.4 GHz IEEE 802.11 b/g/n (20/40 MHz)
  - Bluetooth LE 5 (mesh, 125 Kbps a 2 Mbps)
- GPIO:
  - 45 GPIO programmables
- Interfaces numeriques utiles au projet:
  - 4 SPI
  - 3 UART
  - 2 I2C
  - 2 I2S
  - 1 USB OTG full-speed
  - 1 USB Serial/JTAG
  - 1 SDIO host (2 slots)
- Peripheriques analogiques utiles:
  - 2 ADC SAR 12-bit (jusqu'a 20 canaux)
  - capteur de temperature interne
  - 14 IO tactiles
- Energie et basse consommation:
  - PMU avec 5 modes de puissance
  - coprocessseurs ULP-RISC-V et ULP-FSM

## 2) Securite materielle exploitable

- Secure Boot
- Flash encryption
- OTP 4 Kbit (jusqu'a 1792 bits user)
- Accelerateurs crypto:
  - AES-128/256
  - SHA (Hash)
  - RSA
  - HMAC
  - Digital Signature
  - RNG

## 3) Contraintes a ne pas ignorer

- Certaines alimentations de pins dependent de VDD_SPI / VDD3P3_CPU et de la configuration registre/eFuse.
- Sur ESP32-S3R8V, VDD_SPI est a 1.8 V et GPIO47/GPIO48 (SPICLK_N/SPICLK_P) sont aussi en 1.8 V.
- La plage de temperature ambiante depend de la variante; sur S3R8/S3R8V, activer ECC PSRAM peut monter la limite a 85 C avec reduction de capacite PSRAM (1/16).

## 4) Impacts directs sur le code dans src/base

### 4.1 Audio
- `audio_capture.py`:
  - viser pipeline mono 16 kHz stable
  - surveiller charge CPU + memoire en continu
- `playback.py`:
  - I2S sortie audio, buffer anti-coupure

### 4.2 Transport
- `transport.py`:
  - requetes resilientes (timeouts + retry)
  - budget latence adapte au Wi-Fi 2.4 GHz

### 4.3 Etat appareil
- `device_state.py`:
  - etat runtime compact, faible cout SRAM
  - exploitation GPIO/tactile sans remapping dangereux

### 4.4 Robustesse/energie
- `resilience.py`:
  - mode degrade local + reconnexion progressive
  - hooks pour modes low-power (PMU/ULP) en V2

### 4.5 Runtime
- `runtime.py`:
  - boucle principale non bloquante
  - mecanismes de watchdog logiciel + supervision memoire

## 5) Priorites d'implementation derivees du datasheet

1. Stabilite capture/lecture audio (I2S + buffers)
2. Fiabilite reseau (timeouts, retry, mode degrade)
3. Securisation base device (secure boot/flash encryption prepare)
4. Optimisation conso et tenue memoire
5. Extensions ULP/batterie/RTC en phase suivante

## 6) Checklist de conformite technique (base edge)

- [ ] Le code n'utilise pas de pins reserves a des tensions incompatibles
- [ ] Les chemins critiques audio respectent le budget CPU
- [ ] Les buffers restent dans une enveloppe memoire validee
- [ ] Les erreurs reseau sont recouvrables sans reboot manuel
- [ ] Les options de securite hardware sont prises en compte dans la roadmap firmware

## 7) Integration specifique Waveshare wiki

### 7.1 Variantes carte et perimetre

- La famille est declinee en versions touch et non-touch: verrouiller explicitement la variante cible avant livraison firmware.
- Le wiki indique des differences entre anciennes et nouvelles revisions (microphone remplace), ce qui impacte les performances de reconnaissance vocale et les gains audio.

### 7.2 Toolchain recommandee pour ce projet

- Arduino IDE: prototypage rapide, utile pour validation materielle initiale.
- ESP-IDF: choix prioritaire pour le firmware produit (controle fin des taches, drivers, memoire, debug).
- Contrainte versionnement mentionnee par le wiki:
  - Arduino-ESP32 >= 3.0.2
  - Plugin Espressif IDF >= 5.3.1

### 7.3 Precautions operationnelles (flash/debug)

- En cas de port non detecte ou echec de flash:
  - entrer en download mode via sequence BOOT/RESET,
  - rebrancher USB en maintenant BOOT si necessaire.
- Sur certains environnements, la sortie serie depend de USB CDC (activation au boot selon projet).
- Le wiki signale des problemes possibles si nom d'utilisateur systeme non-ASCII sur certains workflows Windows.

### 7.4 Audio, reconnaissance et memoire

- Le wiki signale que l'activation simultanee de fonctions audio + Bluetooth peut augmenter fortement la pression SRAM.
- Exigence pour `runtime.py` et `resilience.py`:
  - degrader proprement les fonctions non critiques en cas de pression memoire,
  - prioriser capture/reponse vocale et securite d'execution.
- Eviter la reconnaissance vocale pendant lecture haut-parleur dans le flux de validation materielle, sauf strategie AEC explicite.

### 7.5 Peripheriques onboard a prendre en compte

- I2C onboard: adresses mentionnees dans la FAQ wiki: `0x15`, `0x20`, `0x51`.
- Ressources board exposees dans demos wiki: batterie, RTC, TF, capteurs, controle retroeclairage.
- Implication `device_state.py`:
  - etendre etat runtime pour batterie/rtc/tf/backlight sans coupler au pipeline vocal critique.

### 7.6 Exigences de validation derivees du wiki

- Verifier les scenarios de flash/reflash/recovery dans la campagne de robustesse.
- Verifier coexistence Wi-Fi/BLE avec profil audio actif (au moins smoke tests).
- Ajouter une checklist de verification carte SD (format FAT32) pour les tests impliquant medias.
- Documenter explicitement les prerequis de drivers USB selon OS de developpement.

### 7.7 Liens ressources utiles pour implementation

- Schematic board: https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.85/ESP32-S3-Touch-LCD-1.85.pdf
- ESP32-S3 TRM: https://files.waveshare.com/wiki/common/Esp32-s3_technical_reference_manual_en.pdf
- MIC test audio pack: https://files.waveshare.com/wiki/common/MIC_Test_audio.zip
