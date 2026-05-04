# 🟩 Epic EDGE-PHASE0: Bootstrap connectivité base ↔ serveur

**Statut**: 🔴 Not Started  
**Owner**: TBD  
**Timeline**: Semaine 1 (avant tout autre epic EDGE)  
**Estimation**: 15-20 pt (1.5-2 jours)  
**Priority**: 🔴 Bloquant — prérequis de tous les epics EDGE et SRV

---

## 📋 Objectif

Avant de travailler sur l'audio ou le wake word, la base ESP32-S3 doit pouvoir :

1. **Être debuggée via USB-C** (UART/SWD) depuis le PC de développement.
2. **Se connecter au WiFi** via une interface de configuration sur l'écran tactile.
3. **Joindre le serveur** et valider le lien réseau (ping HTTP).

Aucune autre fonctionnalité ne peut être développée ni testée sans ces trois prérequis.

---

## 🎯 Critères d'acceptation

- [ ] La carte ESP32-S3 envoie des logs lisibles sur USB-C (UART over USB, 115200 baud)
- [ ] L'écran tactile affiche une interface de saisie SSID + mot de passe WiFi
- [ ] Les credentials WiFi sont persistés en flash (après reboot, reconnexion auto)
- [ ] La LED/écran indique l'état de connexion WiFi (connecting / connected / error)
- [ ] La base envoie un `GET /health` au serveur et reçoit `200 OK`
- [ ] Le résultat du ping HTTP est visible sur l'écran et dans les logs USB

---

## 📦 Tickets

### EDGE-P0-01: Debug USB-C (UART)

**Objectif**: voir les logs firmware sur le PC via USB-C.

- [ ] Configurer USB CDC (Virtual COM Port) ou UART mappé sur connecteur USB-C
- [ ] Implémenter `printf` redirigé vers USB-CDC / UART
- [ ] Valider reception logs avec `minicom` ou `screen` côté PC
- [ ] Format de log minimal : `[LEVEL] [MODULE] message\n`
- [ ] Test : boot → log `"EDGE booting..."` visible sur PC

**Critère de sortie**: on lit les logs sans avoir besoin de SWD ni de sonde externe.

---

### EDGE-P0-02: Interface WiFi provisioning sur écran tactile

**Objectif**: configurer le WiFi depuis l'écran de la carte, sans recompiler.

#### Flux utilisateur

```
Boot sans credentials → écran affiche "Configuration WiFi"
→ Liste des réseaux détectés (scan WiFi)
→ Tap sur un réseau → saisie mot de passe (clavier tactile à l'écran)
→ Tap "Connecter"
→ Écran affiche "Connexion..." puis "Connecté ✓" ou "Erreur"
→ Credentials sauvegardés en flash (NVS ou équivalent ESP32-S3)
→ Reboot : reconnexion automatique, pas de saisie à répéter
```

#### Sous-tâches

- [ ] Activer le pilote WiFi (STA mode)
- [ ] Implémenter le scan WiFi → liste des SSIDs disponibles
- [ ] Afficher la liste sur l'écran tactile (scroll si besoin)
- [ ] Afficher un clavier tactile minimal pour la saisie du mot de passe
- [ ] Sauvegarder SSID + mot de passe chiffrés en flash (NVS / internal flash)
- [ ] Reconnexion automatique au boot si credentials présents
- [ ] Afficher état connexion : `connecting…` / `connected (IP: x.x.x.x)` / `failed`
- [ ] Log USB : chaque étape du provisioning loguée

**Notes d'implémentation**:
- L'écran est 360×360 tactile capacitif — le clavier doit être adapté à cette résolution.
- Utiliser LVGL (Light and Versatile Graphics Library) si disponible sur la plateforme ESP32-S3 cible, sinon interface minimaliste dessinée manuellement.
- Le clavier n'a pas besoin d'être complet : minuscules + chiffres + `_-@.` suffisent pour les mots de passe WiFi courants. Prévoir un bouton backspace et un bouton confirmer.
- Si le mot de passe doit rester masqué : `*` par défaut avec bouton "afficher".

---

### EDGE-P0-03: Validation lien réseau base ↔ serveur

**Objectif**: confirmer que la base peut joindre le serveur.

- [ ] Implémenter client HTTP minimal (GET sans TLS pour debug initial)
- [ ] Envoyer `GET http://<IP_SERVEUR>:<PORT>/health` au démarrage
- [ ] Afficher résultat sur écran : `Serveur OK ✓` ou `Serveur injoignable ✗`
- [ ] Logger la réponse HTTP (status code + latence) via USB
- [ ] Permettre de changer l'IP serveur depuis l'écran (champ configurable, sauvegardé en flash)
- [ ] Test : couper le serveur → l'écran affiche l'erreur dans les 5 secondes

**Format attendu de la réponse serveur** :
```json
{ "status": "ok", "version": "x.y.z" }
```

---

## 🔗 Dépendances

| Dépendance | Type | Statut |
|---|---|---|
| Carte ESP32-S3 avec écran tactile disponible | Hardware | Requis |
| Pilote LCD + touch initialisé | Firmware | Requis |
| Pilote WiFi STA | Firmware | Requis |
| Serveur local démarré avec endpoint `/health` | Serveur | Requis pour P0-03 |
| Câble USB-C vers PC | Hardware | Requis pour P0-01 |

---

## 🚨 Risques

| Risque | Impact | Mitigation |
|---|---|---|
| Pilote écran tactile non disponible pour ESP32-S3 cible | Bloquant UI | Fallback : provisioning par fichier flash (USB mass storage) ou AT commands série |
| USB CDC non supporté nativement | Debug impossible | Fallback : UART sur header GPIO + adaptateur USB-TTL |
| WiFi instable en phase de test | Perte de temps | Commencer par filaire Ethernet si disponible sur la carte |
| Clavier tactile trop long à implémenter | Retard | Utiliser LVGL keyboard widget ou saisie via terminal USB comme fallback |

---

## 📊 Estimations

| Ticket | Points | Notes |
|---|---|---|
| EDGE-P0-01 (USB debug) | 2 pt | Rapide si USB CDC déjà mappé |
| EDGE-P0-02 (WiFi provisioning) | 10 pt | Clavier tactile = partie complexe |
| EDGE-P0-03 (ping serveur) | 3 pt | Dépend de P0-01 + P0-02 |
| **Total** | **15 pt** | — |

---

## ✅ Definition of Done

- [ ] Logs visibles sur PC via USB-C sans outil externe (juste `minicom` ou terminal série)
- [ ] Provisioning WiFi 100% sur écran : aucun recompile ni fichier à flasher
- [ ] Credentials persistés : reboot → reconnexion auto en < 10 secondes
- [ ] Ping serveur réussi affiché à l'écran ET dans les logs USB
- [ ] Procédure documentée dans [docs/04-engineering/field-tests/](../../../04-engineering/field-tests/)

---

**Créé**: 2026-05-04  
**Précède**: [EDGE-firmware-esp32-s3.md](EDGE-firmware-esp32-s3.md)  
**Roadmap**: [docs/03-delivery/roadmap.md](../roadmap.md)
