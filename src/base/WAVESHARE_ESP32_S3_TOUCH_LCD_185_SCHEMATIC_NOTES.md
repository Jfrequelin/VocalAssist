# Waveshare ESP32-S3-Touch-LCD-1.85 - Notes issues du schema

Source integree:
- Schema board: https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.85/ESP32-S3-Touch-LCD-1.85.pdf

Documentation composant audio associee:
- PCM5101PWR datasheet notes: [src/base/PCM5101PWR_DATASHEET_NOTES.md](src/base/PCM5101PWR_DATASHEET_NOTES.md)

Objectif:
- capturer les informations electriques et de cablage utiles a l'implementation firmware base.

## 1) Composants et blocs identifies dans le schema

- SoC principal: ESP32-S3R8
- Flash externe: W25Q128JVSI (16 MB)
- Audio sortie: PCM5101APWR (DAC I2S)
- Amplification audio: APA2068KAI-TRG
- RTC: PCF85063ATL (bus I2C RTC_SCL/RTC_SDA)
- IMU: QMI8658C (bus IMU_SCL/IMU_SDA)
- Stockage amovible: TF/SD (lignes SDIO + lignes SD_* presentes)
- Ecran LCD:
  - bus parallele data LCD_SDA0..LCD_SDA3
  - signaux de controle LCD_CS, LCD_SCK, LCD_RST, LCD_TE
- Tactile:
  - TP_SCL, TP_SDA, TP_RST, TP_INT
- Alimentation:
  - batterie (BAT), detection BAT_ADC
  - controle BAT_Control
  - entree USB_5V (Type-C)

## 2) Signaux utiles pour le firmware

### 2.1 Audio (I2S / micro / sortie)

- Signaux micro identifies: MIC_SD, MIC_SCK, MIC_WS, MIC_EN
- Signaux I2S sortie identifies: I2S_BCK, I2S_LRCK, I2S_DIN
- Implication firmware:
  - separer strictement pipeline capture micro et pipeline playback,
  - prevoir mecanisme anti-conflit en mode full-duplex,
  - ajouter mode de secours half-duplex si pression memoire/CPU.
  - appliquer les contraintes PCM5101 sur mute pop-free et recovery horloges.

### 2.2 Affichage et tactile

- LCD: lignes data + controle (SDA0..SDA3, CS, SCK, RST, TE)
- Touch: I2C + interruption (TP_SCL/TP_SDA + TP_INT)
- Implication firmware:
  - `device_state` doit inclure un etat UI minimal,
  - gerer debounce et priorite des evenements tactiles,
  - ne pas bloquer la boucle audio avec la boucle UI.

### 2.3 I2C multi-peripheriques

- Plusieurs bus/peripheriques I2C coexistent: RTC, IMU, Touch, I2C externe.
- La FAQ wiki mentionne des adresses onboard: 0x15, 0x20, 0x51.
- Implication firmware:
  - scanner et verifier les devices au boot,
  - gerer timeout I2C et recovery bus,
  - journaliser les peripheriques absents sans crasher la boucle runtime.

### 2.4 Stockage TF/SD

- Lignes SDIO + SD_* presentes dans le schema.
- Implication firmware:
  - format FAT32 attendu pour scenarios medias,
  - fallback propre si carte absente ou non reconnue,
  - ne pas rendre la fonctionnalite vocale dependante de la carte TF.

### 2.5 Alimentation et batterie

- BAT, BAT_ADC, BAT_Control identifies.
- Implication firmware:
  - telemetrie batterie accessible en V1+,
  - garde-fous sur seuil bas batterie (degradation non critique),
  - procedures de redemarrage/recovery robustes quand USB/BAT fluctuent.

## 3) Contraintes de validation derivees du schema

- [ ] Initialisation driver en ordre stable: power -> clocks -> bus -> peripheriques
- [ ] Verification des peripheriques critiques au boot (audio, LCD, touch, I2C, TF)
- [ ] Degradation fonctionnelle si composant absent (ex: TF, touch)
- [ ] Test de coexistence audio + Wi-Fi/BLE sans reset en boucle
- [ ] Test de recovery sur erreurs flash/download (BOOT/RESET)

## 4) Recommandations implementation dans src/base

- `runtime.py`:
  - task driver periodique type Driver_Loop (style FreeRTOS) pour operations peripheriques
  - supervision et watchdog logiciel
- `audio_capture.py` et `playback.py`:
  - abstraction claire des broches/signaux I2S
  - profilage memoire sur charge vocale continue
- `device_state.py`:
  - etat runtime enrichi: ui, battery, storage, sensors
- `resilience.py`:
  - circuits de recovery I2C/SD/audio
  - mode degrade quand un sous-systeme est indisponible

## 5) Points a confirmer avant codage firmware final

- Revision exacte de carte en production (ancienne/nouvelle) et impact micro
- Mapping final des broches dans BSP cible (ESP-IDF)
- Politique full-duplex vs half-duplex en exploitation vocale
- Budget memoire cible avec audio + BLE actifs simultanement
