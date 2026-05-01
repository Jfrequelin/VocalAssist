# Index des datasheets composants (base ESP32-S3)

Perimetre:
- composants identifies dans le schema Waveshare ESP32-S3-Touch-LCD-1.85
- liens verifies automatiquement (HTTP) le 2026-05-01

## 1) Datasheets valides (accessibles)

| Composant | Role | Statut | Datasheet |
|---|---|---|---|
| ESP32-S3 | SoC principal | OK (200) | https://files.waveshare.com/wiki/common/Esp32-s3_datasheet_en.pdf |
| PCM5101 (PCM5101PWR) | DAC audio I2S | OK (200) | https://files.waveshare.com/wiki/common/TexasInstruments-PCM5101PWR.pdf |
| QMI8658A / QMI8658C | IMU | OK (200) | https://files.waveshare.com/wiki/common/QMI8658A.pdf |
| PCF85063ATL (famille PCF85063A) | RTC | OK (200) | https://www.nxp.com/docs/en/data-sheet/PCF85063A.pdf |
| W25Q128JVSI | Flash SPI | OK (200) | https://www.winbond.com/resource-files/w25q128jv%20revf%2003272018%20plus.pdf |
| AO3401 / AO3401A | MOSFET | OK (200) | https://aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf |
| ICS-43434 | Microphone MEMS (revision board recente) | OK (200) | https://invensense.tdk.com/wp-content/uploads/2015/02/ICS-43434-datasheet-v1.3.pdf |
| MSM261S4030H0R | Microphone MEMS (ancienne revision board) | OK (200) | https://files.waveshare.com/upload/0/01/MSM261S4030H0R.pdf (miroir: https://datasheet.lcsc.com/lcsc/1811141610_MEMSIC-MSM261S4030H0R_C258248.pdf) |
| MBR230LSFT1G | Diode Schottky | OK (200) | https://www.onsemi.com/pdf/datasheet/mbr230lsft1-d.pdf |

## 2) Liens trouves mais non exploitables directement

| Composant | Statut | Lien teste | Note |
|---|---|---|---|
| B5819WS | Restreint (403) | https://www.diodes.com/assets/Datasheets/ds30217.pdf | Le lien repond mais bloque selon la source/IP. Chercher miroir ou ref exacte constructeur. |

## 3) Datasheets non resolves (a completer)

| Composant | Statut | Lien teste | Action recommandee |
|---|---|---|---|
| ETA6098 | Introuvable (ERR) | https://www.etasolution.com/uploads/pdf/ETA6098.pdf | Confirmer la reference exacte sur le schema BOM puis chercher dans le portail ETA Solution. |
| APA2068KAI-TRG | Introuvable (404) | https://www.anpec.com.tw/ashx_prod_file.ashx?prod_id=497&file_name=APA2068KAI.pdf&dir=009 | Verifier la reference package exacte (KAI-TRG) et rechercher sur site Anpec/miroirs distributeur. |

## 4) Sources board-level utiles

- Wiki board: https://www.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.85
- Schema board: https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.85/ESP32-S3-Touch-LCD-1.85.pdf
- TRM ESP32-S3: https://files.waveshare.com/wiki/common/Esp32-s3_technical_reference_manual_en.pdf

## 5) Couverture actuelle

- Composants critiques couverts pour demarrer l'implementation firmware: SoC, DAC, IMU, RTC, Flash, MOSFET, micro recent et micro legacy.
- Points restants pour completude hardware totale: ETA6098, APA2068KAI-TRG, B5819WS (lien restreint).
