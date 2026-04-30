# 🔐 Security & Secrets Detection

## Overview

System automatisé pour détecter et prévenir le commit/push de secrets:

- **Pre-commit hook**: Vérifie format tickets + pas d'accident .tickets-local
- **Pre-push hook**: 🔴 **NOUVEAU** — Détecte secrets avant push GitHub
- **Audit script**: Scanner manuel pour faux positifs + mode fix interactif

---

## 🚀 Quick Start

### Installation des hooks

```bash
./scripts/install-hooks.sh
```

Cela installe:
- ✅ `pre-commit` — Validation tickets
- ✅ `pre-push` — Détection secrets (NOUVEAU)

### Avant de pousser vers GitHub

Test automatique (git hook):
```bash
git push
# Le hook détecte les secrets et refuse le push
```

Test manuel:
```bash
# Scanner fichiers stagés
python3 scripts/audit-secrets.py --staged

# Scanner un dossier spécifique
python3 scripts/audit-secrets.py --dir src/

# Scanner avec suggestions interactives
python3 scripts/audit-secrets.py --fix
```

---

## 📊 Ce qui est détecté

Le hook pre-push refuse de pousser si:

| Pattern | Exemple | Action |
|---------|---------|--------|
| Private keys | `-----BEGIN PRIVATE KEY-----` | Block |
| API keys | `api_key=sk_live_123abc...` | Block |
| GitHub tokens | `gh_abc123...` | Block |
| AWS credentials | `AKIA0123456789ABCDEF` | Block |
| Slack tokens | `xoxb-123...` | Block |
| Database URLs | `postgres://user:pass@host` | Block |
| JWT tokens | `eyJ...eyJ...sig` | Block |
| .env files | `.env`, `.env.local` | Block |
| .pem/.key files | `*.pem`, `*.key` | Block |

---

## ✅ Checklist Sécurité Avant Push

```bash
# 1. Vérifier manuellement les différences
git diff --cached | grep -i "password\|secret\|token\|api"
# → Ne rien trouver

# 2. Scanner avec l'outil
python3 scripts/audit-secrets.py --staged
# → "✅ Aucun secret détecté!"

# 3. Vérifier pas de .env stagés
git diff --cached --name-only | grep -E ".env|.pem|.key|credentials"
# → (rien)

# 4. Push!
git push
# → Hook pre-push fait une dernière vérification
```

---

## 🎯 Conventions pour Secrets

### ✅ BON: Utiliser env vars

```python
import os

# API keys depuis l'environnement
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LEON_API_URL = os.getenv("LEON_API_URL")  # eg: https://leon.local:8080
LEON_API_ENDPOINT = os.getenv("LEON_API_ENDPOINT")  # eg: /api/query
LEON_TIMEOUT_SECONDS = os.getenv("LEON_TIMEOUT_SECONDS")  # eg: 5
LEON_RETRY_ATTEMPTS = os.getenv("LEON_RETRY_ATTEMPTS")  # eg: 1
LEON_RETRY_BACKOFF_SECONDS = os.getenv("LEON_RETRY_BACKOFF_SECONDS")  # eg: 0
HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL")
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN")
HOME_ASSISTANT_LIGHT_SALON = os.getenv("HOME_ASSISTANT_LIGHT_SALON")
WEATHER_PROVIDER_URL_TEMPLATE = os.getenv("WEATHER_PROVIDER_URL_TEMPLATE")
MUSIC_PROVIDER_URL = os.getenv("MUSIC_PROVIDER_URL")
MUSIC_PROVIDER_AUTH_TOKEN = os.getenv("MUSIC_PROVIDER_AUTH_TOKEN")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Exemple fichier .env (dans .gitignore):
# GITHUB_TOKEN=ghp_xxxxxxxxxxxx
# LEON_API_URL=https://leon.example.com
# LEON_API_ENDPOINT=/api/query
# LEON_TIMEOUT_SECONDS=5
# LEON_RETRY_ATTEMPTS=1
# LEON_RETRY_BACKOFF_SECONDS=0
# HOME_ASSISTANT_URL=https://ha.example.com
# HOME_ASSISTANT_TOKEN=ha_xxxxxxxxxxxx
# HOME_ASSISTANT_LIGHT_SALON=light.salon
# WEATHER_PROVIDER_URL_TEMPLATE=https://weather.example/api/current?city={city}
# MUSIC_PROVIDER_URL=https://music.example/api/playback
# MUSIC_PROVIDER_AUTH_TOKEN=music_xxxxxxxxxxxx
# DB_PASSWORD=MySecurePassword123
```

### ❌ MAUVAIS: Hardcoder les secrets

```python
# ❌ JAMAIS DANS LE CODE
GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnop"
API_KEY = "sk_live_123abc456def789"
DB_URL = "postgres://admin:password123@db.com/prod"

# ❌ JAMAIS EN COMMENTAIRES NON PLUS
# Leon token: secret123xyz
# Admin password: AdminPass123!
```

---

## 🚨 Si un secret a été accidentellement commité

### Étape 1: Annuler le commit (immédiatement!)

```bash
# Voir l'historique
git log --oneline | head -5

# Si le secret est dans le dernier commit
git reset HEAD~1
# Ou si c'est plus loin:
git revert <commit_hash>
```

### Étape 2: Nettoyer le fichier

```bash
# Éditer le fichier, retirer le secret
vim src/foo.py

# OU retirer le fichier de git
git rm --cached .env

# Ajouter à .gitignore
echo ".env" >> .gitignore
```

### Étape 3: Recommitter sans secret

```bash
git add -A
git commit -m "Remove secrets from tracked files (Fixes #SEC-001)"
```

### Étape 4: Régénérer le credentials

- Si c'était un vrai token/key: **régénérer immédiatement**
- Inclure dans la notification à l'équipe

### Étape 5: Vérifier l'historique

```bash
# Vérifier que le secret n'est plus dans l'historique
git log --all --full-history -S "secret_text" -- .
# ou pour les fichiers
git log --all --full-history -- .env
```

---

## 🔧 Customiser la Détection

### Ajouter des patterns personnalisés

Éditer [scripts/audit-secrets.py](scripts/audit-secrets.py):

```python
PATTERNS = {
    "PRIVATE_KEY": r"-----BEGIN.*PRIVATE KEY-----",
    "MY_CUSTOM_PATTERN": r"my_secret_[a-z0-9]{32}",  # ← Ajouter ici
}
```

### Ignorer des faux positifs

Créer/éditer [.secretsignore](.secretsignore):

```
# Faux positifs d'exemples
docs/examples/**
tests/fixtures/fake-secrets.py

# Strings qui contiennent "secret" mais ce n'est pas une clé
src/assistant/intents.py  # Contains "remind" intent (not credential)
```

---

## 📝 Notes pour les Devs

1. **Ne jamais** committer `.env` ou fichiers avec secrets
2. **Toujours** utiliser et documenter env vars requises
3. **GitHub PRs**: Revoir les diffs pour secrets avant merge
4. **CI/CD**: Ne jamais logger les env vars en debug mode

### Template .env pour team

Créer `.env.template` ou `.env.example` (sans vraies valeurs):

```bash
# .env.example (safe to commit)
GITHUB_TOKEN=your_github_token_here
LEON_API_URL=https://leon.example.com:8080
LEON_API_ENDPOINT=/api/query
LEON_TIMEOUT_SECONDS=5
LEON_RETRY_ATTEMPTS=1
LEON_RETRY_BACKOFF_SECONDS=0
HOME_ASSISTANT_URL=https://ha.example.com
HOME_ASSISTANT_TOKEN=your_home_assistant_token_here
HOME_ASSISTANT_LIGHT_SALON=light.salon
WEATHER_PROVIDER_URL_TEMPLATE=https://weather.example/api/current?city={city}
MUSIC_PROVIDER_URL=https://music.example/api/playback
MUSIC_PROVIDER_AUTH_TOKEN=your_music_provider_token_here
DB_PASSWORD=your_db_password_here
```

Instructions:
```bash
cp .env.example .env
# Edit .env with real values
```

---

## 🔗 Ressources

- [copilot-instructions.md](copilot-instructions.md#securite--détection-de-secrets-critique) — Règles Copilot
- [.git/hooks/pre-push](.git/hooks/pre-push) — Hook automatique
- [scripts/audit-secrets.py](scripts/audit-secrets.py) — Scanner manuel
- [.secretsignore](.secretsignore) — Ignorer faux positifs
- [docs/bonnes-pratiques/03-securite-et-git.md](docs/bonnes-pratiques/03-securite-et-git.md) — Full security guide

---

## ❓ FAQ

**Q: Le hook pre-push bloque mon push.**

A: 
1. Vérifier: `python3 scripts/audit-secrets.py --staged`
2. Si faux positif: ajouter à `.secretsignore`
3. Contourner (⚠️ attention): `git push --no-verify`

**Q: Où mettre les secrets pour le dev local?**

A: Dans un fichier `.env`:
```bash
# .env (dans .gitignore)
GITHUB_TOKEN=your_real_token
```

Puis charger dans Python:
```python
from dotenv import load_dotenv
load_dotenv()
token = os.getenv("GITHUB_TOKEN")
```

**Q: Comment partager les secrets avec l'équipe?**

A: Jamais via Git! Utiliser:
- 1Password / LastPass (password manager)
- HashiCorp Vault (enterprise)
- Environment variables in CI/CD secrets
- Fichier `.env` sur disque local protégé

**Q: Un secret fut commité il y a 6 mois. C'est grave?**

A: Oui. L'historique Git le rend public:
1. Régénérer le credential immédiatement
2. Nettoyer l'historique Git (force push + rebase — attention!)
3. Utiliser `git-filter-branch` ou `BFG Repo-Cleaner` si critique

---

**Created**: 2026-04-30  
**Updated**: SECURITY_AND_SECRETS.md
