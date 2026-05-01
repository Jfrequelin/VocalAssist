# Synchronisation Tickets GitHub ↔️ Markdown Local

Scripts pour synchroniser les tickets GitHub (issues/PRs) avec des fichiers markdown locaux (ignorés par git).

## 📦 Setup

### 1. Authentification GitHub sans exposer le token

```bash
# Recommande: login via navigateur, sans manipuler le token en clair
./scripts/gh-auth-secure.sh --web

# Alternative: saisie masquee d'un token personnel
./scripts/gh-auth-secure.sh --token
```

Le script de synchronisation utilise ensuite automatiquement, dans cet ordre:
- `--token` passe au script
- `GITHUB_TOKEN`
- le token deja stocke par `gh auth login`

### 2. Installation dépendances

Le script n'a pas de dependance Python externe obligatoire.

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

## Publication du backlog local vers GitHub

Une fois `gh` authentifie, vous pouvez publier les tickets macro et sous-tickets prepares dans `doc/tickets`.

```bash
# Verifier auth
gh auth status

# Voir ce qui sera cree sans rien publier
python3 scripts/publish_backlog_to_github.py --repo Jfrequelin/VocalAssist --all --dry-run

# Publier les macros seulement
python3 scripts/publish_backlog_to_github.py --repo Jfrequelin/VocalAssist --macros

# Publier ensuite les sous-tickets
python3 scripts/publish_backlog_to_github.py --repo Jfrequelin/VocalAssist --subtickets
```

## Validation standard d'un ticket

Le script suivant applique le workflow de traitement ticket:
- py_compile
- tests
- passe Pylance (pyright si disponible)
- passe pylint sans exemption de regles (score minimal par defaut: 9.0)

```bash
# Exemple sur un ticket
python3 scripts/validate_ticket.py \
  --files src/assistant/prototype_voice.py src/assistant/voice_pipeline.py \
  --tests tests/test_voice_pipeline.py tests/test_orchestrator.py

# Changer explicitement le seuil minimal pylint
python3 scripts/validate_ticket.py \
  --files src/assistant/prototype_voice.py \
  --tests tests/test_voice_pipeline.py \
  --pylint-fail-under 9.0

# Mode strict (echoue si pyright/pylint absents)
python3 scripts/validate_ticket.py \
  --files src/assistant/prototype_voice.py \
  --tests tests/test_voice_pipeline.py \
  --strict-pylance --strict-pylint
```

### Options disponibles

```bash
python3 scripts/sync_tickets.py --help
```

| Option | Par défaut | Description |
|--------|-----------|-------------|
| `--owner` | `Jfrequelin` | Propriétaire du repo GitHub |
| `--repo` | `VocalAssist` | Nom du repo |
| `--token` | `gh auth token` ou `$GITHUB_TOKEN` | Token GitHub |
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

### Mapping macro -> issues

La synchronisation génère aussi une vue stable d'alignement backlog local/GitHub:

- `doc/tickets/macro_issue_mapping.json`
- `doc/tickets/MACRO-ISSUE-MAPPING.md`

Ces fichiers regroupent les issues par macro (`MACRO-XXX`) et par type (`macro`, `task`,
`subticket`, `atomic-task`) pour vérifier rapidement qu'il n'y a pas d'ambiguïté.

## 🔄 Workflow recommandé

### Quotidien en boucle courte

```bash
# Le matin: sync des tickets du sprint
./scripts/sync.sh open --label "Sprint 2 weeks"

# Consulter en markdown:
cat .tickets-local/INDEX.md
```

## Robustesse Edge (satellite)

Variables utiles pour le prototype edge:

- `EDGE_BACKEND_URL`: URL backend cible (défaut `http://127.0.0.1:8081`)
- `EDGE_DEVICE_ID`: identifiant du satellite
- `EDGE_WAKE_WORD`: mot-clé local (défaut `nova`)
- `EDGE_SEND_RETRY_ATTEMPTS`: nombre de retries réseau (défaut `2`)
- `EDGE_SEND_RETRY_BACKOFF_SECONDS`: backoff entre retries (défaut `0.1`)

Matrice de tests terrain et stratégie réseau: `docs/EDGE-NETWORK-VALIDATION.md`.

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
