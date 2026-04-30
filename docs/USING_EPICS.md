# 📚 Using Épics: Guide Complet

## 🎯 Qu'est-ce qu'un épic?

Un **épic** est une fonctionnalité majeure décomposée en:
- **Description complète**: Justification, architecture
- **Critères d'acceptation**: Définition du "done"
- **Sous-tâches**: 8-12 tickets GitHub à créer
- **Estimations**: Story points + facteurs de risque
- **Dépendances**: Blocked by / blocks
- **Tests**: Scénarios de validation
- **Notes techniques**: Code samples, architecture

## 📋 Les 5 épics du projet

| Epic | Focus | Lead | Timeline |
|------|-------|------|----------|
| 🟦 **EDGE** | Firmware ESP32-S3 | - | Week 1 |
| 🟩 **SRV** | STT/TTS server | - | Week 1 |
| 🟧 **ORCH** | Orchestrator local-first | - | Week 1-2 |
| 🟣 **DOM** | Home Assistant integration | - | Week 2 |
| 🔴 **OBS** | Observability (cross-cutting) | - | Week 1-2 |

Voir [docs/03-delivery/epics/README.md](docs/03-delivery/epics/README.md) pour l'overview.

---

## 🚀 Workflow: De l'épic au ticket GitHub

### Étape 1: Lire l'épic (15 min)

```bash
# Lire épic EDGE en entier
cat docs/03-delivery/epics/EDGE-firmware-esp32-s3.md

# Lire juste l'overview de tous les épics
cat docs/03-delivery/epics/README.md
```

### Étape 2: Parser les subtasks (5 min)

```bash
# Extraire les tickets à créer
python3 scripts/make-tickets-from-epics.py --epic EDGE

# Voir tous les épics
python3 scripts/make-tickets-from-epics.py --all
```

### Étape 3: Créer les tickets GitHub (30 min)

**Option A: Manuelle** (plus de contrôle)

```bash
# Aller sur GitHub
# https://github.com/Jfrequelin/VocalAssist/issues/new

# Créer 10 issues:
# EDGE-01, EDGE-02, ..., EDGE-10
# Chacun avec:
# - Title: "[EPIC EDGE] <titre_subtask>"
# - Description: [copier de l'épic]
# - Labels: EDGE, Sprint 2 weeks, Priority-1
# - Milestone: (vide pour MVP)
```

**Option B: Script** (faster, quand implémenté)

```bash
# TODO: scripts/create-tickets-from-epics.sh
# ./scripts/create-tickets-from-epics.sh --epic EDGE --create
```

### Étape 4: Synchroniser localement (5 min)

```bash
./scripts/sync.sh

# Vérifier que les tickets sont présents
cat .tickets-local/INDEX.md | grep EDGE
```

### Étape 5: Développer selon le plan (Week 1-2)

```bash
# Créer une branche pour l'épic
git checkout -b feat/EDGE-firmware

# Développer les subtasks dans l'ordre:
# Day 1: EDGE-01 + EDGE-02
# Day 2: EDGE-03 + EDGE-04 + EDGE-05
# Day 3: EDGE-06 + EDGE-07 + EDGE-08
# Day 4: EDGE-09 + EDGE-10 (tests)

# Committer avec références:
git commit -m "feat: I2S mic + buffer circulaire (Fixes #EDGE-001)"
git commit -m "feat: Opus codec integration (Fixes #EDGE-002)"
...

# Créer PR
git push origin feat/EDGE-firmware
# Créer pull request avec: "Fixes #EDGE-001, #EDGE-002, ..."
```

---

## 📊 Epic Structure (Template)

Chaque épic contient:

```markdown
# 🟦 Epic NAME

**Statut**: 🔴 Not Started | 🟡 In Progress | 🟢 Done
**Owner**: TBD
**Timeline**: Semaines X-Y
**Estimation**: ZZ pt (days)
**Priority**: 🔴 Critique | 🟠 Haute | 🟡 Moyenne

---

## 📋 Description
[What & Why]

## 🎯 Critères d'acceptation
[Acceptance criteria]

## 📦 Sous-tâches (Tickets)
### Phase 1: Task Group 1
**EPIC-01**: Subtitle
- [ ] Checklist 1
- [ ] Checklist 2

---

## 📊 Estimations
[Story points breakdown]

## 🔗 Dépendances
[Blocked by / Blocks]

## 🚨 Risques + Mitigations
[Risk matrix]

## 📝 Notes d'implémentation
[Code samples, architecture diagrams]

## ✅ Definition of Done
[Final checklist]
```

---

## 🔄 Workflow Continu

### En parallèle avec le développement:

1. **Quotidien (10 min)**
   ```bash
   # Sync tickets mis-à-jour
   ./scripts/sync.sh
   
   # Consulter les tickets du jour
   cat .tickets-local/INDEX.md | grep "EDGE.*Priority-1"
   ```

2. **Fin de tâche (2 min)**
   ```bash
   # Committer avec ref ticket
   git commit -m "feat: XYZ (Fixes #42)"
   
   # Push
   git push origin feat/EDGE-firmware
   
   # Créer/mettre à jour PR
   ```

3. **Fin de jour (5 min)**
   ```bash
   # Syncer (les tickets GitHub seront mis-à-jour)
   ./scripts/sync.sh
   
   # Vérifier progression
   cat .tickets-local/manifest.json | grep total_issues
   ```

---

## 📈 Tracking Progression

### Par ticket
```bash
# Voir l'état d'un ticket
cat .tickets-local/0001-*.md | grep "État:"

# Extraire tous les tickets Status=open
grep -l "État.*open" .tickets-local/*.md | wc -l
```

### Par épic
```bash
# Compter tickets EDGE créés
ls .tickets-local/EDGE-*.md 2>/dev/null | wc -l

# Compter tickets EDGE fermés
grep -l "État.*closed" .tickets-local/ | grep -c EDGE || echo "0"
```

### Dashboard simple
```bash
# Nombre de tickets par épic
for epic in EDGE SRV ORCH DOM OBS; do
  echo -n "$epic: "
  ls .tickets-local/${epic}-*.md 2>/dev/null | wc -l
done
```

---

## 🎓 Bonnes Pratiques

### ✅ À faire

1. **Référencer l'épic dans commits**
   ```bash
   git commit -m "feat: Ajouter STT (Fixes #EDGE-001, #SRV-002)"
   ```

2. **Découper en tickets petits** (3-8 points max)
   - Plus facile à estimer
   - Plus rapide à itérer
   - Plus facile à tester

3. **Synchroniser quotidiennement**
   ```bash
   ./scripts/sync.sh  # Takes <1 sec
   ```

4. **Écrire tests dès le début**
   - TDD: tests avant code
   - Tous les tickets doivent avoir tests

5. **Documenter dès qu'on découvre**
   - Blocker? Ajouter au risque section
   - Nouvelle dépendance? Signaler dans dépendances

### ❌ À ne pas faire

1. **Laisser un ticket ouvert + pas de commit**
   - Tracker: "Je travaille dessus" et commiter au moins 1x/jour

2. **Créer des tickets trop grands** (>13 points)
   - Découper en 2-3 tickets plus petits

3. **Ignorer les critères d'acceptation**
   - Chaque acceptance criterion = min 1 test

4. **Committer sans référence ticket**
   ```bash
   # ❌ Mauvais
   git commit -m "Fix bug"
   
   # ✅ Bon
   git commit -m "Fix: STT latency (Fixes #SRV-002)"
   ```

---

## 🔍 Debugging: Tracer un problème

### Si un ticket est bloqué

1. **Chercher dans l'épic**
   ```bash
   grep -A5 "EPIC-XX:" docs/03-delivery/epics/*.md | grep -i "risk\|depend"
   ```

2. **Vérifier dépendances**
   ```bash
   cat docs/03-delivery/epics/EDGE-firmware-esp32-s3.md | grep -A10 "Dépendances"
   ```

3. **Consulter les notes techniques**
   ```bash
   cat docs/03-delivery/epics/SRV-stc-tts-server.md | grep -A20 "Architecture"
   ```

4. **Ouvrir une issue de blocker**
   ```bash
   git commit -m "docs: EDGE-05 blocked by SRV-01 not available"
   ```

---

## 📚 Resources

- 📋 [Épics Overview](docs/03-delivery/epics/README.md)
- 🟦 [EDGE Firmware](docs/03-delivery/epics/EDGE-firmware-esp32-s3.md)
- 🟩 [SRV Server](docs/03-delivery/epics/SRV-stc-tts-server.md)
- 🟧 [ORCH Orchestrator](docs/03-delivery/epics/ORCH-orchestrator-local-first.md)
- 🟣 [DOM Home Assistant](docs/03-delivery/epics/DOM-home-assistant.md)
- 🔴 [OBS Observability](docs/03-delivery/epics/OBS-observability.md)
- 📊 [Sprint 2 Weeks](docs/03-delivery/sprint-2-weeks.md)
- 📈 [6-Month Roadmap](docs/03-delivery/roadmap.md)

---

## ❓ FAQ

**Q: Combien de temps pour créer les tickets?**  
A: 30 min (manuel) to 5 min (avec script quand implémenté)

**Q: Puis-je travailler sur 2 épics à la fois?**  
A: Oui, mais éviter multitasking excessif (max 2 parallèles)

**Q: Que faire si l'estimation était mauvaise?**  
A: Commit to GitHub + note dans le ticket + update épic si pattern

**Q: Qui assigné les tickets?**  
A: Lead dev du sprint (TBD) ou self-assignment

**Q: Tickets finis mais pas de PR créée?**  
A: `git commit --amend` ou créer PR + link au ticket

---

**Last Updated**: 2026-04-30  
**Author**: VocalAssist Team
