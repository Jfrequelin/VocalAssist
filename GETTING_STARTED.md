# 🚀 Getting Started - Système de Tickets & Workflow

## ✅ Installation rapide

```bash
# 1. Cloner le repo
git clone https://github.com/Jfrequelin/VocalAssist.git
cd VocalAssist

# 2. Installer les git hooks
./scripts/install-hooks.sh

# 3. (Optionnel) Configurer le token GitHub pour limite élevée
export GITHUB_TOKEN='ghp_votre_token'

# 4. Synchroniser les tickets
./scripts/sync.sh
```

## 📋 Utilisation quotidienne

### Consulter les tickets

```bash
# Sync depuis GitHub (80ms avg)
./scripts/sync.sh

# Lire l'index
cat .tickets-local/INDEX.md

# Lire un ticket par numéro
cat .tickets-local/0042-*.md
```

### Commencer à développer

```bash
# 1. Créer une branche feature
git checkout -b feat/mon-feature

# 2. Développer & committer
git commit -m "feat: Ajouter STT avec Whisper (Fixes #42)"
# ← Automatiquement vérifié par pre-commit hook

# 3. Pusher & créer PR
git push origin feat/mon-feature
# Puis ouvrir PR sur GitHub en référençant le ticket

# 4. Après merge, la sync marquera le ticket 'closed'
./scripts/sync.sh all
```

## 🔧 Configuration avancée

### Automation quotidienne avec cron

```bash
# Ajouter à crontab (chaque matin à 8h)
0 8 * * * cd /chemin/vers/VocalAssist && ./scripts/sync.sh

# Ou juste avant le start d'une session de dev
echo "alias dev-tickets='cd $PWD && ./scripts/sync.sh && cat .tickets-local/INDEX.md'" >> ~/.bashrc
```

### CI/CD Integration

Voir [GitHub Actions example](scripts/README.md#-cicd-integration) pour auto-sync sur chaque commit.

## 📊 Vérifier la setup

```bash
# Vérifier que les hooks sont installés
test -x .git/hooks/pre-commit && echo "✅ Pre-commit hook OK" || echo "❌ Hook missing"

# Vérifier l'accès à l'API GitHub
python3 scripts/sync_tickets.py --state open --help | head -3

# Lister les fichiers générés
ls -la .tickets-local/ | head -10
```

## 📚 Documentation complète

- **[WORKFLOW.md](WORKFLOW.md)** — Workflow complet (GitHub → Local → Dev → PR)
- **[scripts/README.md](scripts/README.md)** — Détails des scripts & options
- **[docs/03-delivery/sprint-2-weeks.md](docs/03-delivery/sprint-2-weeks.md)** — Tickets du sprint actuel
- **[docs/03-delivery/roadmap.md](docs/03-delivery/roadmap.md)** — Roadmap 6 mois

## ⚙️ Options du script de sync

```bash
# Sync tous les tickets ouverts
./scripts/sync.sh

# Sync tous (ouverts + fermés)
./scripts/sync.sh all

# Sync avec filtre par label
./scripts/sync.sh open --label "Sprint 2 weeks"

# Sync avec plusieurs labels (ET logique)
python3 scripts/sync_tickets.py --label "SRV" --label "Priority-1"

# Afficher l'aide
python3 scripts/sync_tickets.py --help
```

## 🐛 Troubleshooting

### "GitHub API rate limited"
→ Configure `GITHUB_TOKEN` pour passer de 60 à 5000 req/h

### ".tickets-local accidentellement committés"
→ Les hooks git l'empêchent. Ou: `git reset .tickets-local/`

### "Script sync_tickets.py non trouvé"
→ Assurez-vous d'être à la racine du repo: `cd VocalAssist`

### "python3: command not found"
→ Installer Python 3.10+ (macOS: `brew install python3`, Ubuntu: `apt install python3`)

## 📌 Bonnes pratiques

✅ **À faire:**
```bash
git commit -m "feat: Ajouter feature X (Fixes #42)"  # Référence le ticket
git commit -m "refactor: Nettoyer code Y (#99)"      # Fix ou mention
```

❌ **À ne pas faire:**
```bash
git commit -m "Work in progress"                     # Sans ticket ref
git add .tickets-local/                              # Accumulera des conflits
cat .tickets-local/*.md > local_snapshot.txt         # Fichiers jetables
```

## 🎯 Prochaines étapes

1. **Créer les premiers tickets** sur GitHub avec labels (`EDGE`, `SRV`, `OBS`, etc.)
2. **Synchroniser**: `./scripts/sync.sh`
3. **Consulter**: `cat .tickets-local/INDEX.md`
4. **Attaquer les sprints** selon [sprint-2-weeks.md](docs/03-delivery/sprint-2-weeks.md)

---

**Besoin d'aide?** Voir [scripts/README.md](scripts/README.md) pour tous les détails.

**Questions?** Ouvrir une issue: https://github.com/Jfrequelin/VocalAssist/issues
