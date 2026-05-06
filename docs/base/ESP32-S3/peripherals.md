# Peripheriques ESP32-S3

## Peripheriques geres par la base

## Audio
- ES7210: ADC microphone (I2C 0x40)
- ES8311: DAC haut-parleur (I2C 0x18)
- NS4150B: ampli, pilote par PA_CTRL GPIO15

### ES7210 — séquence d'init critique (Waveshare V2)

**Contexte :** La carte Waveshare ESP32-S3-Touch-LCD-1.85C-BOX V2 embarque
l'ES7210 (ADC 4 canaux) couplé à l'ES8311 (DAC). La séquence d'init documentée
dans le datasheet générique de l'ES7210 est **incompatible** avec cette révision
de carte — les registres semblent accepter les écritures (I2C retourne OK) mais
les valeurs ne sont pas prises en compte. Résultat observable : micro silencieux
(`peak=0`) sur tous les cycles de capture.

**Cause racine :** Après le reset logiciel (`reg 0x00 = 0xFF`), il faut
**obligatoirement** écrire `reg 0x00 = 0x41` pour sortir du mode reset. Sans
cette écriture, le chip reste en reset permanent et ignore toutes les écritures
suivantes. Ce comportement est confirmé par le driver officiel ESP-ADF v2.7.

**Registres clés corrigés** (vs. l'ancienne séquence incorrecte) :

| Reg  | Avant (KO) | Après (ESP-ADF) | Rôle |
|------|-----------|-----------------|------|
| 0x00 | `0xFF` seul | `0xFF` → délai → `0x41` | **Sortie reset — critique** |
| 0x11 | `0x0C` | `0x60` | Format 16-bit (bits[7:5]=011) |
| 0x40 | `0xC3` | `0x43` | Analog init, vdda=3.3V |
| 0x41 | `0xC3` | `0x70` | MIC1/2 bias 2.87V |
| 0x42 | `0x08` | `0x70` | MIC3/4 bias 2.87V |
| 0x43/44 | `0x0C` | `0x1D` | bit4=ADC enable + gain 36dB |
| 0x47–0x4A | absents | `0x08` chacun | MIC power ON |
| 0x09/0x0A | absents | `0x30` | Timing cycles chip/power-on |
| 0x20–0x23 | absents | HPF coefficients | Filtres haute-coupure |
| 0x04/0x05 | absents | `0x01/0x00` | LRCK divider (256 pour 16kHz) |
| 0x01 final | `0x30` | `0x00` | Activer tous les clocks (start) |

**Référence :** Driver `espressif/esp-adf` v2.7,
`components/audio_hal/driver/es7210/es7210.c`, fonctions `es7210_adc_init()`
et `es7210_start()`.

**Validation :** Firmware `test-micro` (capture continue 500ms, stats L/R),
cycles #35+ montrent `peak=692–874` avec signal ambiant vs. `peak=0` avant fix.

**Code :** `src/audio/mod.rs` — constante `ES7210_SEQ`.

## Affichage
- ST77916: LCD rond 360x360 via QSPI
- backlight sur GPIO5

## Tactile
- CST816S via I2C
- interruption tactile sur GPIO4

## Expander I/O
- TCA9554PWR via I2C
- reset LCD / touch et lignes annexes

## Reseau
- modem Wi-Fi ESP32-S3
- connectivite serveur et fallback degrade

## Helpers board support

Le code specifique a la carte doit vivre dans `src/peripherals/`:
- boot button / factory reset
- capacites declarees au serveur
- autres aides de board support a faible niveau

Le `main` ne doit pas contenir de logique detaillee de manipulation materielle; il delegue a `app.rs` et aux modules `peripherals/`.
