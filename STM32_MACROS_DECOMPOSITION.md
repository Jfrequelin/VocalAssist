# STM32 MACROS - Décomposition Complète

**Date**: 1 mai 2026  
**Status**: ✅ DÉCOMPOSITION COMPLÈTE

---

## Résumé de la Structure

### Vue Générale
- **Macros Principales**: 8 (#149-156)
- **Tickets Parent Récapitulatifs**: 8 (#294-301)
- **Tâches (T1-T4 par macro)**: 32 (#166-197)
- **Sous-tickets (S1-S3 par tâche)**: 96 (#198-293)
- **Total Tickets STM32**: 144 tickets

### Hierarchy Complète

```
MACRO (Parent)
  ├── Ticket Récapitulatif "Sous-tickets"
  │   └── Contient map vers tous T/S
  │
  ├── T1 (Tâche 1)
  │   ├── S1 (Sous-ticket 1)
  │   ├── S2 (Sous-ticket 2)
  │   └── S3 (Sous-ticket 3)
  │
  ├── T2 (Tâche 2)
  │   ├── S1
  │   ├── S2
  │   └── S3
  │
  ├── T3 (Tâche 3)
  │   ├── S1
  │   ├── S2
  │   └── S3
  │
  └── T4 (Tâche 4)
      ├── S1
      ├── S2
      └── S3
```

---

## Détail par Macro

### MACRO-006: Transport Audio et Synchronisation Réseau (#149)
**Récapitulatif**: #294

| Tâche | Issues | Sous-tickets |
|-------|--------|--------------|
| T1: Protocole et transport | #166 | #198, #199, #200 |
| T2: Wake word et VAD | #167 | #201, #202, #203 |
| T3: Sync et correlation | #168 | #204, #205, #206 |
| T4: Tests terrain | #169 | #207, #208, #209 |

---

### MACRO-007: Gestion d'État et Contrôle LED (#150)
**Récapitulatif**: #295

| Tâche | Issues | Sous-tickets |
|-------|--------|--------------|
| T1: State model | #170 | #210, #211, #212 |
| T2: LED RGB | #171 | #213, #214, #215 |
| T3: Button control | #172 | #216, #217, #218 |
| T4: Device controller | #173 | #219, #220, #221 |

---

### MACRO-008: Intents Audio Système (#151)
**Récapitulatif**: #296

| Tâche | Issues | Sous-tickets |
|-------|--------|--------------|
| T1: Stop media/mute | #174 | #222, #223, #224 |
| T2: Volume control | #175 | #225, #226, #227 |
| T3: Intents critiques | #176 | #228, #229, #230 |
| T4: Feedback | #177 | #231, #232, #233 |

---

### MACRO-009: Intents Informatifs (#152)
**Récapitulatif**: #297

| Tâche | Issues | Sous-tickets |
|-------|--------|--------------|
| T1: RTC/heure | #178 | #234, #235, #236 |
| T2: Météo/temp | #179 | #237, #238, #239 |
| T3: Agenda | #180 | #240, #241, #242 |
| T4: Latence | #181 | #243, #244, #245 |

---

### MACRO-010: Intents Domotique (#153)
**Récapitulatif**: #298

| Tâche | Issues | Sous-tickets |
|-------|--------|--------------|
| T1: Light control | #182 | #246, #247, #248 |
| T2: Music/media | #183 | #249, #250, #251 |
| T3: Reminders | #184 | #252, #253, #254 |
| T4: Integration | #185 | #255, #256, #257 |

---

### MACRO-011: Synthèse Vocale et Playback (#154)
**Récapitulatif**: #299

| Tâche | Issues | Sous-tickets |
|-------|--------|--------------|
| T1: Piper TTS | #186 | #258, #259, #260 |
| T2: I2S output | #187 | #261, #262, #263 |
| T3: Volume/mute | #188 | #264, #265, #266 |
| T4: Latence | #189 | #267, #268, #269 |

---

### MACRO-012: Résilience (#155)
**Récapitulatif**: #300

| Tâche | Issues | Sous-tickets |
|-------|--------|--------------|
| T1: WiFi handling | #190 | #270, #271, #272 |
| T2: HTTP errors | #191 | #273, #274, #275 |
| T3: EEPROM persist | #192 | #276, #277, #278 |
| T4: Monitoring | #193 | #279, #280, #281 |

---

### MACRO-013: Pipeline Complet (#156)
**Récapitulatif**: #301

| Tâche | Issues | Sous-tickets |
|-------|--------|--------------|
| T1: Local E2E | #194 | #282, #283, #284 |
| T2: Remote E2E | #195 | #285, #286, #287 |
| T3: Error recovery | #196 | #288, #289, #290 |
| T4: Stress/perf | #197 | #291, #292, #293 |

---

## Mapping Complet

### Tickets Parents (Macros)
```
#149 → MACRO-006 Transport Audio
#150 → MACRO-007 Gestion d'État/LED
#151 → MACRO-008 Intents Audio Système
#152 → MACRO-009 Intents Informatifs
#153 → MACRO-010 Intents Domotique
#154 → MACRO-011 Synthèse Vocale
#155 → MACRO-012 Résilience
#156 → MACRO-013 Pipeline Complet
```

### Tickets Récapitulatifs (Sous-tickets map)
```
#294 → Sous-tickets MACRO-006
#295 → Sous-tickets MACRO-007
#296 → Sous-tickets MACRO-008
#297 → Sous-tickets MACRO-009
#298 → Sous-tickets MACRO-010
#299 → Sous-tickets MACRO-011
#300 → Sous-tickets MACRO-012
#301 → Sous-tickets MACRO-013
```

### Tâches T1-T4 par Macro
```
MACRO-006: #166-169 (T1-T4)
MACRO-007: #170-173 (T1-T4)
MACRO-008: #174-177 (T1-T4)
MACRO-009: #178-181 (T1-T4)
MACRO-010: #182-185 (T1-T4)
MACRO-011: #186-189 (T1-T4)
MACRO-012: #190-193 (T1-T4)
MACRO-013: #194-197 (T1-T4)
```

### Sous-tickets S1-S3 par Tâche
```
MACRO-006-T1: #198-200 (S1-S3)
MACRO-006-T2: #201-203 (S1-S3)
MACRO-006-T3: #204-206 (S1-S3)
MACRO-006-T4: #207-209 (S1-S3)
... (32 tâches × 3 = 96 sous-tickets)
MACRO-013-T4: #291-293 (S1-S3)
```

---

## Adoption de Standards

Cette décomposition suit exactement le même pattern que les macros assistant:

**Pattern Côté Assistant**:
- MACRO-001 (#1) → MACRO-005 (#5)
- Tickets Récapitulatifs (#9-#16) 
- T1-T4 pour chaque macro
- S1-S3 pour chaque tâche

**Pattern Côté STM32 (Appliqué)**:
- MACRO-006 (#149) → MACRO-013 (#156) ✅
- Tickets Récapitulatifs (#294-#301) ✅
- T1-T4 pour chaque macro (#166-#197) ✅
- S1-S3 pour chaque tâche (#198-#293) ✅

---

## Statut de Décomposition

- ✅ 8 Macros principales créées
- ✅ 8 Tickets récapitulatifs avec hyperliens
- ✅ 32 Tâches (T1-T4) créées
- ✅ 96 Sous-tickets (S1-S3) créés
- ✅ Structure cohérente avec pattern assistant
- ✅ Navigation complète entre niveaux

---

## Prochaines Étapes

Chaque sous-ticket S1-S3 est maintenant prêt pour:
1. **Détailement des AC** (Acceptance Criteria)
2. **Estimation d'effort** (story points)
3. **Assignation** aux développeurs
4. **Planification** en sprints
5. **Exécution** avec traçabilité complète

---

**Créé**: 1 mai 2026  
**Total Tickets Créés**: 144  
**Pattern**: Réplique conforme pattern assistant MACRO-001 à MACRO-005
