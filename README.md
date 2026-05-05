# AssistantVocal — Edge firmware ESP32-S3

> 🚧 **Work in progress** — Phase 0 (provisioning) terminée. Phase 1 (pipeline vocal) en cours de planification.

Assistant vocal embarqué sur satellite edge **Waveshare ESP32-S3-Touch-LCD-1.85C-BOX-EN**.
Firmware Rust + ESP-IDF, interface tactile complète, connexion WiFi + serveur Leon.

---

## Ce qui fonctionne déjà

- ✅ Driver LCD ST77916 QSPI 360×360 (artefacts corrigés)
- ✅ Driver touch CST816S I2C
- ✅ Provisioning WiFi entièrement tactile (scan, sélection, clavier, NVS)
- ✅ Configuration serveur IP/port avec test connexion en ligne
- ✅ Persistance NVS (credentials WiFi + adresse serveur)
- ✅ Factory reset via appui long BOOT (3 s)
- ✅ Ping serveur GET `/health` avec affichage latence/version

## Suite prévue (Phase 1)

- 🔲 Capture audio micro 16 kHz PCM
- 🔲 Wake word detection local
- 🔲 Voice Activity Detection (VAD)
- 🔲 Envoi audio → serveur Leon → réponse TTS
- 🔲 Écran état READY (idle / listening / thinking / speaking / error)
- 🔲 Gestion déconnexion/reconnexion WiFi en runtime

---

---

## Matériel cible

| Composant | Référence |
|-----------|-----------|
| SoC | ESP32-S3 (dual-core Xtensa LX7, 240 MHz) |
| PSRAM | 8 MB OPI (SPIRAM_MODE_OCT activé) |
| Flash | 16 MB QIO |
| LCD | ST77916, 360×360 px, QSPI 4-bit |
| Touch | CST816S, I2C 0x15 |
| GPIO expander | TCA9554PWR |

---

## État Phase 0 — Provisioning (✅ terminé)

### WiFi provisioning (tactile)

- Scan des réseaux → liste scrollable avec pagination tactile
- Sélection SSID par tap
- Saisie mot de passe : clavier 3 modes (lettres / chiffres / symboles)
- Masquage `*` + révélation dernier caractère 700 ms (smartphone style)
- Bouton RETOUR pour changer de réseau
- Persistance NVS + reconnexion automatique au boot suivant

### Configuration serveur (tactile)

- Champs IP + Port pré-remplis depuis NVS (défaut : `192.168.1.100:8080`)
- Bascule entre champs par tap
- Bouton **TEST CONNECT** : ping GET `/health` sans sauvegarder
- Bouton **OK / SAUVER** : persistance NVS
- Ping final avec affichage latence et version serveur

### Infrastructure

- Driver LCD ST77916 QSPI (3 bugs critiques corrigés : NOP, fill_rect, RAMWR)
- Driver touch CST816S I2C (ID chip 0xB5 confirmé)
- Factory reset via appui long BOOT GPIO0 (3 s) — efface WiFi + config serveur
- Surveillance runtime BOOT (polling 200 ms en boucle principale)
- PSRAM 8 MB OPI activée (`sdkconfig.defaults`)

---

## Structure du projet

```
src/base/firmware/esp32-s3/
├── src/
│   ├── main.rs          # Boot, phases, boucle principale
│   ├── ui.rs            # Tous les écrans tactiles (provisioning, config, statuts)
│   ├── lcd/mod.rs       # Driver ST77916 QSPI
│   ├── touch/mod.rs     # Driver CST816S I2C
│   ├── wifi/mod.rs      # WifiManager, NVS credentials, scan, connect
│   └── server/mod.rs    # ServerPing, NVS adresse, GET /health
├── sdkconfig.defaults   # Config ESP-IDF (flash 16 MB, PSRAM OPI, USB-JTAG)
├── partitions.csv       # Table de partitions (NVS 64 KB, app 6 MB)
└── Cargo.toml
```

---

## Build & Flash

**Prérequis :** toolchain Xtensa (`cargo +esp`), ESP-IDF v5.x sourced, `espflash`

```bash
cd src/base/firmware/esp32-s3
. ~/esp/esp-idf/export.sh

# Compiler
cargo +esp build --target xtensa-esp32s3-espidf

# Flasher
espflash flash --port /dev/ttyACM0 target/xtensa-esp32s3-espidf/debug/assistant-edge

# Flasher + monitor série
espflash flash --port /dev/ttyACM0 --monitor target/xtensa-esp32s3-espidf/debug/assistant-edge
```

---

## Factory reset

Maintenir le bouton **BOOT (GPIO0)** appuyé pendant **3 secondes** au boot ou en cours d'utilisation.
Efface les credentials WiFi et la config serveur en NVS, puis redémarre.

---

## Documentation

Voir [`docs/`](docs/README.md) pour l'architecture, les décisions produit, la roadmap et les tests terrain.
