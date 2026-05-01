# Implémentation de la Contrainte Open Source pour STM32 Macros

**Date**: 1 mai 2026  
**Status**: ✅ COMPLÈTE  
**Commit**: `834d0ee`

---

## Objectif

Ajouter une **directive obligatoire open source** à travers tous les documents de projet pour assurer que les 8 macros STM32 (MACRO-006 → MACRO-013) n'utilisent que des solutions open source (MIT, Apache 2.0, BSD, GPL compatible).

## Travaux Réalisés

### 1. Mise à Jour de copilot-instructions.md

**Section Ajoutée**: "Contrainte: Priorité aux Solutions Open Source"

**Contenu**:
- Principes directeurs pour sélection de dépendances (open source prioritaire)
- Stack open source recommandé par couche:
  - **Backend/API**: FastAPI, SQLAlchemy, Celery, Redis, PostgreSQL
  - **Vocal/Audio**: Faster-Whisper, Piper, PocketSphinx, librosa
  - **Firmware**: Rust, Cargo, CMake, FreeRTOS, stm32l4xx-hal
  - **ML**: PyTorch, scikit-learn, ONNX
  - **Infra**: Docker, Kubernetes, GitHub Actions, Prometheus, Grafana

- Table des alternatives open source aux solutions propriétaires (Google TTS → Piper, etc.)

- Checklist d'audit pour chaque dépendance:
  ```bash
  # 1. Vérifier licence (MIT/Apache/BSD/GPL)
  # 2. Vérifier activité GitHub (< 3 mois)
  # 3. Vérifier taille/overhead
  # 4. Vérifier sécurité (pip-audit, cargo audit)
  ```

**Fichier**: [copilot-instructions.md](copilot-instructions.md#contrainte-priorité-aux-solutions-open-source)

---

### 2. Mise à Jour de STM32_MACROS_ROADMAP.md

**A. Section "Contrainte: Solutions Open Source"** (début du roadmap)

**Table d'Approbation par Composant**:
| Composant | Solution | Licence | Raison |
|-----------|----------|---------|--------|
| Language | Rust | MIT/Apache 2.0 | Sécurité mémoire |
| Audio Synthesis | Piper | MIT | Local, français, embarquable |
| Audio Capture | Standard I2S | MIT/Apache | STM32 open drivers |
| Wake Word | PocketSphinx/Porcupine alt. | BSD/MIT | Décentralisé, français |
| VAD | webrtcvad | BSD | Qualité OpenAI |
| HTTP Client | smoltcp/esp-idf | MIT/Apache | Léger, bare-metal |
| Build | Cargo | MIT/Apache | Standard Rust |
| RTOS | FreeRTOS | MIT | Ultra-lean |
| HAL | stm32l4xx-hal | MIT/Apache | Community-maintained |

**Embedded Rust Ecosystem Approuvé**:
- cortex-m (MIT) - ARM Cortex-M support
- embedded-hal (MIT/Apache) - Trait abstractions
- heapless (MIT) - No_std collections
- defmt (MIT) - Embedded formatting
- smoltcp (MIT) - Bare-metal TCP/IP
- esp-idf - ESP32 support
- stm32l4xx-hal (MIT) - STM32L4 HAL

**Interdictions Explicites**:
- ❌ Google Cloud Speech API (propriétaire, cloud-only)
- ❌ Azure Speech Services (propriétaire)
- ❌ Nuance Dragon (propriétaire, coûteux)
- ❌ Proprietary RTOS (QNX, Integrity)
- ❌ Vendor lock-in (AWS IoT Core only, Azure only)

**Validation de Dépendance** (checklist):
```bash
# 1. Vérifier licence - cargo tree
cargo tree | grep -E "MIT|Apache|BSD|GPL"

# 2. Vérifier no_std support
cargo build --release --no-default-features

# 3. Vérifier taille
cargo build --release --target thumbv7em-none-eabihf
ls -lh target/thumbv7em-none-eabihf/release/

# 4. Vérifier activité GitHub
gh repo view <owner>/<crate> --json updatedAt
```

**Fichier**: [STM32_MACROS_ROADMAP.md](STM32_MACROS_ROADMAP.md#-contrainte-solutions-open-source)

---

### B. Section "KPIs et Success Criteria" - Ajout de Conformité Open Source

**Nouveaux KPIs**:
- ✅ 100% composants open source (MIT/Apache/BSD/GPL compatible)
- ✅ Zéro dépendance propriétaire ou cloud-only
- ✅ `cargo tree` montre toutes les licences compatibles
- ✅ Respect SPDX pour tous les identifiants
- ✅ Aucun service Freemium obligatoire
- ✅ Auditabilité par la communauté

**Fichier**: [STM32_MACROS_ROADMAP.md](STM32_MACROS_ROADMAP.md#kpis-et-success-criteria)

---

### 3. Documentation dans les 8 Tickets GitHub

**Tickets Mis à Jour**: #149 (MACRO-006) → #156 (MACRO-013)

**Commentaire Enfant Ajouté à Chaque Ticket**:

```markdown
## 📌 Contrainte Open Source

**Tous les composants dans cette macro DOIVENT être open source** 
(MIT, Apache 2.0, BSD, GPL 3.0 compatible).

### ✅ Approuvé pour cette macro
- Rust ecosystem (cortex-m, embedded-hal, heapless)
- Piper TTS (MIT - Rhasspy)
- WebRTC VAD (BSD)
- smoltcp / esp-idf (MIT/Apache)
- FreeRTOS (MIT)
- stm32l4xx-hal / stm32h7xx-hal (MIT)

### ❌ À ÉVITER
- Google Cloud Speech
- Azure Speech Services
- Proprietary RTOS (QNX, Integrity)
- Vendor lock-in solutions

**Avant merge**: Vérifier avec `cargo tree` que toutes 
les dépendances ont des licences compatibles.
```

**Nombre de Commentaires Ajoutés**: 8 (un par macro)

---

## Validation Complète

### ✅ Doc Chaîne
- [x] copilot-instructions.md - Nouvelle section "Contrainte: Priorité aux Solutions Open Source"
- [x] STM32_MACROS_ROADMAP.md - Section "Contrainte: Solutions Open Source" + Table approbation + KPIs
- [x] 8 tickets GitHub (149-156) - Commentaires enfants avec approuvé/interdit

### ✅ Git/GitHub
- [x] Commit local: `834d0ee` (docs: add open-source-first constraint for MACRO-006..MACRO-013)
- [x] Push vers main: `origin/main` confirmé
- [x] Hooks pre-push: Pas de secrets détectés ✅

### ✅ Conformité
- [x] Tous les composants documentés ont des licences open source
- [x] Checklist d'audit fournie pour futures dépendances
- [x] Pas d'ambiguïté sur approuvé vs interdit
- [x] Référence claire vers STM32_MACROS_ROADMAP.md dans chaque ticket

---

## Impact

### Pour les Développeurs
- ✅ Directive claire: utiliser open source
- ✅ Checklist rapide pour valider une dépendance
- ✅ Stack recommandée par composant
- ✅ Alternatives documentées aux solutions propriétaires

### Pour le Projet
- ✅ Zéro vendor lock-in
- ✅ Full auditability par la communauté
- ✅ Coûts prévisibles (aucun service SaaS obligatoire)
- ✅ Alignement avec philosophie open source

### Pour les Macros STM32 (006-013)
- ✅ Tous les tickets ont contrainte explicite
- ✅ Peut commencer implementation avec confiance dans choix technologiques
- ✅ Rust + cortex-m + Piper = stack 100% open source validé

---

## Prochaines Étapes (Recommendations)

1. **MACRO-007** (État/LED): Commencer avec Rust + cortex-m-rt (approuvé ✅)
2. **MACRO-011** (TTS): Intégrer Piper Rust binding (approuvé ✅)
3. **MACRO-006** (Transport): Utiliser smoltcp (approuvé ✅)
4. **Audit régulier**: `cargo tree` à chaque ajout de dépendance

---

**Statut Final**: ✅ COMPLÈTE ET VALIDÉE

Tous les documents sont à jour, tous les tickets sont documentés, et le commit est publié sur GitHub.
