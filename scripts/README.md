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

## Smoke-test deployment docker-compose

Depuis la racine du repo:

```bash
./scripts/smoke-test.sh
```

Avec cleanup automatique:

```bash
./scripts/smoke-test.sh --teardown
```

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

Lancement rapide du profil terrain (Linux):

```bash
# Mode local in-process (sans backend externe)
./scripts/run_edge_field_profile.sh local

# Mode HTTP (backend docker-compose sur 127.0.0.1:18081)
./scripts/run_edge_field_profile.sh http
```

Surcharges courantes avant lancement:

```bash
ASSISTANT_TESTBENCH_CAPTURE_DEVICE=hw:CARD=Generic_1,DEV=0 \
ASSISTANT_TESTBENCH_PLAYBACK_DEVICE=hw:CARD=Generic_1,DEV=0 \
./scripts/run_edge_field_profile.sh local
```

Casque Bluetooth (PipeWire/Pulse):

- Le script `run_edge_field_profile.sh` selectionne maintenant automatiquement:
  - `ASSISTANT_TESTBENCH_CAPTURE_DEVICE=pulse`
  - `ASSISTANT_TESTBENCH_PLAYBACK_DEVICE=default`
  - `ASSISTANT_TESTBENCH_REPLAY_CAPTURE=false`

- Commande recommandee pour test micro BT:

```bash
TESTBENCH_MIC_SECONDS=2 ./scripts/run_edge_field_profile.sh http
```

- Optionnel: forcer explicitement la capture BT via Pulse:

```bash
ASSISTANT_TESTBENCH_CAPTURE_DEVICE=pulse \
ASSISTANT_TESTBENCH_PLAYBACK_DEVICE=default \
ASSISTANT_TESTBENCH_REPLAY_CAPTURE=false \
./scripts/run_edge_field_profile.sh http
```

- Sensibilite STT utile pour micro Bluetooth (niveau d'entree plus faible):

```bash
ASSISTANT_STT_MIN_AVG_AMPLITUDE=40 \
ASSISTANT_STT_NO_SPEECH_THRESHOLD=0.6 \
./scripts/run_edge_field_profile.sh http
```

- Fin de phrase automatique (actif par defaut):

```bash
ASSISTANT_TESTBENCH_PHRASE_MODE=true \
ASSISTANT_TESTBENCH_END_SILENCE_SECONDS=1.0 \
ASSISTANT_TESTBENCH_MAX_CAPTURE_SECONDS=10 \
./scripts/run_edge_field_profile.sh http
```

- Reglage VAD fin de phrase (casque Bluetooth):

```bash
ASSISTANT_TESTBENCH_VAD_START_THRESHOLD=60 \
ASSISTANT_TESTBENCH_VAD_SILENCE_THRESHOLD=30 \
./scripts/run_edge_field_profile.sh http
```

Troubleshooting micro/speaker Linux:

- Si `arecord` remonte `Nombre de canaux non disponible`, le testbench applique un fallback automatique (stereo) sur la capture ALSA.
- Pour verifier le speaker analogique local:

```bash
speaker-test -D hw:CARD=Generic_1,DEV=0 -c 2 -t sine -f 440 -l 1
```

- Pour verifier le TTS systeme:

```bash
spd-say "Test audio assistant vocal"
```

- Si le debut de phrase est tronque (`assistant` -> `sistant`), activer/garder le warm-up TTS (actif par defaut):

```bash
ASSISTANT_TTS_WARMUP=true ./scripts/run_edge_field_profile.sh http
```

- Pour forcer un moteur TTS:

```bash
ASSISTANT_TTS_ENGINE=spd-say ./scripts/run_edge_field_profile.sh http
# ou
ASSISTANT_TTS_ENGINE=espeak ./scripts/run_edge_field_profile.sh http
```

## Proxy LLM (llm_proxy_server.py)

Remplace `leon-mock` par un vrai LLM via tout endpoint compatible OpenAI (GitHub Models, Ollama, OpenAI...).

### Activation avec Docker Compose

```bash
# 1. Créer .env à partir de .env.example
cp .env.example .env
# Éditer .env avec vos valeurs (LEON_API_URL, LLM_PROXY_*)

# 2. Lancer la stack avec le profil llm
docker compose --profile llm up --build -d

# 3. Lancer le testbench en mode LLM
TESTBENCH_MIC_SECONDS=3 ./scripts/run_edge_field_profile.sh http
```

### Exemples de configuration .env

**GitHub Models (avec GITHUB_TOKEN):**
```env
LEON_API_URL=http://llm-proxy:1337
LLM_PROXY_ENDPOINT=https://models.inference.ai.azure.com
LLM_PROXY_API_KEY=<votre GITHUB_TOKEN>
LLM_PROXY_MODEL=gpt-4o-mini
```

**Ollama local:**
```env
LEON_API_URL=http://llm-proxy:1337
LLM_PROXY_ENDPOINT=http://host.docker.internal:11434/v1
LLM_PROXY_API_KEY=ollama
LLM_PROXY_MODEL=qwen2.5:3b
```

### Test rapide du proxy seul

```bash
# Démarrer le proxy directement (hors Docker)
LLM_PROXY_ENDPOINT=https://models.inference.ai.azure.com \
LLM_PROXY_API_KEY=$GITHUB_TOKEN \
LLM_PROXY_MODEL=gpt-4o-mini \
python scripts/llm_proxy_server.py

# Test
curl -s http://localhost:1337/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelle heure est-il ?"}' | python -m json.tool
```

## Benchmark latence vocale E2E

Script reproductible pour valider le SLO de latence médiane E2E.

```bash
./.venv/bin/python scripts/benchmark_voice_latency.py
```

Sorties par défaut:
- `docs/03-delivery/voice-latency-benchmark-latest.md`
- `data/voice_latency_samples.latest.json`

Options utiles:
- `--input-json <fichier>`: utilise des samples fournis
- `--sample-count <n>` et `--seed <n>`: génération synthétique reproductible
- `--max-median-ms <ms>`: seuil SLO (défaut 1800)

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
