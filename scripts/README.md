# Synchronisation Tickets GitHub ↔️ Markdown Local

Scripts pour synchroniser les tickets GitHub (issues/PRs) avec des fichiers markdown locaux (ignorés par git).

## 📦 Setup

### 1. Configuration Token GitHub

```bash
# Générer un token: https://github.com/settings/tokens
# Permissions minimum: repo (publique) ou private_repo (privée)

export GITHUB_TOKEN='ghp_votre_token_ici'
```

### 2. Installation dépendances

```bash
pip3 install requests
```

## 🚀 Utilisation

### Synchroniser tous les tickets ouverts (par défaut)

```bash
./scripts/sync.sh
# ou directement:
python3 scripts/sync_tickets.py
```

### Synchroniser avec filtres

```bash
# Tous les tickets (ouverts + fermés)
./scripts/sync.sh all

# Filtrer par sprint
./scripts/sync.sh open --label "Sprint 2 weeks"

# Filtrer par plusieurs labels
python3 scripts/sync_tickets.py --state open --label "SRV" --label "Priority-1"
```

### Options disponibles

```bash
python3 scripts/sync_tickets.py --help
```

| Option | Par défaut | Description |
|--------|-----------|-------------|
| `--owner` | `Jfrequelin` | Propriétaire du repo GitHub |
| `--repo` | `VocalAssist` | Nom du repo |
| `--token` | `$GITHUB_TOKEN` | Token GitHub (var env par défaut) |
| `--state` | `open` | État: `open`, `closed`, ou `all` |
| `--label` | - | Filtrer par label (répétable) |

## 📂 Structure locale

```
.tickets-local/                    # Répertoire .gitignore
├── INDEX.md                      # Vue d'ensemble tous les tickets
├── manifest.json                 # Métadonnées dernière sync
├── 0001-Feature_request.md       # Tickets individuels
├── 0042-Bug_fix.md
└── ...
```

### Fichier INDEX.md

Voir rapidement l'état:
```bash
cat .tickets-local/INDEX.md
```

### Fichier manifest.json

```json
{
  "synced_at": "2026-04-30T14:32:10.123456",
  "owner": "Jfrequelin",
  "repo": "VocalAssist",
  "state": "open",
  "labels": null,
  "total_issues": 15,
  "created_files": 12,
  "updated_files": 3
}
```

## 🔄 Workflow recommandé

### Quotidien en boucle courte

```bash
# Le matin: sync des tickets du sprint
./scripts/sync.sh open --label "Sprint 2 weeks"

# Consulter en markdown:
cat .tickets-local/INDEX.md
```

### En CI/CD

```yaml
# .github/workflows/sync-tickets.yml
name: Sync Tickets
on:
  schedule:
    - cron: '0 8 * * *'  # Chaque jour à 8h
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip3 install requests
      - run: python3 scripts/sync_tickets.py --state "open"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## ⚠️ Important

- ✅ Les fichiers .md dans `.tickets-local/` sont **locaux seulement**
- ✅ Ne jamais commiter directement dans `.tickets-local/`
- ✅ Éditer les tickets sur GitHub directement (les .md seront regénérés)
- ✅ `.tickets-local/` dans `.gitignore` → jamais versionné

## 🐛 Troubleshooting

### "GitHub API rate limited"

```bash
# Ajouter un token GitHub:
export GITHUB_TOKEN='ghp_...'
# Passe de 60 req/h (anonyme) à 5000 req/h (authentifié)
```

### "ModuleNotFoundError: requests"

```bash
pip3 install requests
```

### "jq: command not found" (si utilisation jq)

```bash
# macOS
brew install jq

# Ubuntu/Debian
apt-get install jq
```

## 🔌 Intégration VS Code

Ajouter à `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Sync GitHub Tickets",
      "type": "shell",
      "command": "./scripts/sync.sh",
      "presentation": {
        "reveal": "always",
        "panel": "new"
      },
      "group": {
        "kind": "build",
        "isDefault": false
      }
    }
  ]
}
```

Puis lancer via: `Ctrl+Shift+B` → "Sync GitHub Tickets"

## 📖 Format des fichiers markdown

Chaque ticket génère un fichier avec:

```markdown
# [42] Titre du ticket

**État**: open
**Créé**: 2026-04-20T10:30:00Z
**Mis à jour**: 2026-04-30T14:32:10Z
**Assigné à**: Jfrequelin

## Labels
`SRV`, `Priority-1`

## Milestone
Sprint 2 weeks

## Description
[Contenu du corps du ticket]

## Métadonnées JSON
[Données brutes structurées]
```

---

**Dernière update**: 2026-04-30  
**Auteur**: VocalAssist Team
