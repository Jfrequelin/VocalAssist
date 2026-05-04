# Wiring - ESP32-S3-Touch-LCD-1.85C

Source analysee:
- PDF constructeur: [ESP32-S3-Touch-LCD-1.85C_V2.pdf](ESP32-S3-Touch-LCD-1.85C_V2.pdf)

## Resume rapide

Le schema confirme une architecture basee sur ESP32-S3R8 avec:
- LCD ST77916 en QSPI 4-bit (pas SPI 3 fils classique)
- Touch CST816S en I2C
- RTC sur le meme bus I2C principal
- GPIO expander TCA9554 pour des signaux "EXIO" (reset LCD/touch, etc.)

## Mapping principal LCD/touch (valide firmware)

| Fonction | Net schema | Broche |
|---|---|---|
| Touch interrupt | TP INT(GPIO4) | IO4 |
| Backlight PWM | BL PWM | IO5 |
| I2C SCL (touch) | TP SCL | IO10 |
| I2C SDA (touch) | TP SDA | IO11 |
| LCD TE | LCD TE | IO18 |
| LCD chip select | LCD CS | IO21 |
| LCD QSPI clock | LCD SCK | IO40 |
| LCD QSPI data3 | LCD SDA3 | IO41 |
| LCD QSPI data2 | LCD SDA2 | IO42 |
| LCD QSPI data1 | LCD SDA1 | IO45 |
| LCD QSPI data0 | LCD SDA0 | IO46 |
| Touch reset (via expander) | TP RST | Extend IO1 |
| LCD reset (via expander) | LCD RST | Extend IO2 |
| USB D- | D_N | GPIO19 |
| USB D+ | D_P | GPIO20 |

## Signaux via GPIO expander (EXIO)

Le schema montre un TCA9554PWR pour des E/S "Extend IOx".
Correspondances visibles dans la matrice:

| Fonction | Ligne matrice |
|---|---|
| TP RST | Extend IO1 |
| LCD RST | Extend IO2 |
| SD D3 | Extend IO3 |
| EXIO5 | Extend IO5 |
| EXIO6 | Extend IO6 |
| EXIO7 | Extend IO7 |
| EXIO8 | Extend IO8 |

## UART et connecteurs debug

| Signal | Net |
|---|---|
| UART TXD | GPIO43 |
| UART RXD | GPIO44 |

Le schema inclut aussi un header expose avec USB_5V, BAT, GND, I2C, UART et quelques GPIO/EXIO.

## SD Card (TF)

La matrice indique au minimum:
- SD SCK sur GPIO14
- SD D0 sur GPIO16
- SD CMD sur GPIO17
- SD D3 via Extend IO3

## Notes d'integration firmware

- Pour le LCD, utiliser une interface QSPI 4 data + CS + SCK, commande en 32 bits (mode panel IO SPI ESP-IDF).
- Le reset LCD n'est pas sur un GPIO direct ESP32-S3, il passe par la couche EXIO.
- Le touch partage le bus I2C principal (GPIO10/11) avec le RTC.

## Points a verifier sur banc (recommande)

1. Adresse I2C exacte du TCA9554 sur votre revision de carte.
2. Sequence EXIO pour TP_RST et LCD_RST au boot (etat initial, timings).
3. Etat BL_PWM au boot (niveau par defaut avant takeover firmware).
4. Mapping SD complet (D1/D2) si mode SDIO 4-bit requis.
