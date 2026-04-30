# Copilot Instructions - AssistantVocal

Ces instructions guident GitHub Copilot pour ce repository.

## Contexte projet

- Projet Python d'assistant vocal type Alexa.
- Priorite actuelle: definition, simulation, puis prototype local.
- Structure de reference:
  - `main.py`
  - `src/assistant/`
  - `docs/`

## Documentation de reference

- [README.md](README.md)
- [docs/README.md](docs/README.md)
- [docs/01-vision/product-definition.md](docs/01-vision/product-definition.md)
- [docs/01-vision/product-decisions.md](docs/01-vision/product-decisions.md)
- [docs/02-architecture/system-architecture.md](docs/02-architecture/system-architecture.md)
- [docs/02-architecture/interfaces-and-contracts.md](docs/02-architecture/interfaces-and-contracts.md)
- [docs/03-delivery/roadmap.md](docs/03-delivery/roadmap.md)
- [docs/03-delivery/sprint-2-weeks.md](docs/03-delivery/sprint-2-weeks.md)
- [docs/04-engineering/coding-guidelines.md](docs/04-engineering/coding-guidelines.md)
- [docs/04-engineering/testing-and-kpi.md](docs/04-engineering/testing-and-kpi.md)
- [docs/05-research/assistant-benchmark.md](docs/05-research/assistant-benchmark.md)
- [docs/bonnes-pratiques-codage.md](docs/bonnes-pratiques-codage.md)
- [docs/bonnes-pratiques/01-principes-generaux.md](docs/bonnes-pratiques/01-principes-generaux.md)
- [docs/bonnes-pratiques/02-tests-et-documentation.md](docs/bonnes-pratiques/02-tests-et-documentation.md)
- [docs/bonnes-pratiques/03-securite-et-git.md](docs/bonnes-pratiques/03-securite-et-git.md)
- [docs/bonnes-pratiques/04-conventions-python.md](docs/bonnes-pratiques/04-conventions-python.md)
- [docs/bonnes-pratiques/05-definition-of-done.md](docs/bonnes-pratiques/05-definition-of-done.md)
- [docs/99-legacy/README.md](docs/99-legacy/README.md)

## Regles de code

- Respecter les conventions de [docs/bonnes-pratiques-codage.md](docs/bonnes-pratiques-codage.md).
- Garder les fonctions courtes et a responsabilite unique.
- Ajouter des types sur les fonctions publiques et des noms explicites.
- Eviter les changements de style non necessaires hors du scope.

## Regles metier assistant vocal

- Separer clairement le parsing d'intentions de la couche interface.
- Ajouter les nouveaux intents dans un module centralise.
- Conserver un comportement deterministe en mode simulation.
- Ne jamais casser les commandes existantes sans mise a jour des scenarios.

## Qualite et validation

- Proposer des tests pour toute nouvelle logique metier.
- Verifier qu'un lancement local fonctionne apres modification.
- Mettre a jour la documentation lorsque le comportement change.

## Securite

- Ne jamais introduire de secrets en dur dans le code.
- Valider et normaliser les entrees externes.
- Eviter de logger des donnees sensibles.
## Securite - Détection de secrets (CRITIQUE)

**AVANT TOUT PUSH: Vérifier systématiquement l'absence de secrets!**

### ✅ À faire

- Utiliser des variables d'environnement pour TOUS les secrets:
  ```python
  API_KEY = os.getenv("API_KEY")  # ✅ Bon
  LEON_TOKEN = os.getenv("LEON_TOKEN")
  DB_PASSWORD = os.getenv("DB_PASSWORD")
  ```

- Ne JAMAIS commiter:
  - Clés privées (*.pem, *.key, id_rsa)
  - Tokens/API keys
  - Passwords, credentials
  - .env, .env.local, secrets.json
  - AWS/Azure/GCP credentials
  - Database connection strings

- Mettre les fichiers sensibles dans `.gitignore`:
  ```
  .env
  .env.*.local
  *.pem
  *.key
  credentials.json
  secrets/*
  /config/secrets.yaml
  ```

### ❌ À ne PAS faire

```python
# ❌ MAUVAIS - Secrets en dur
GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuv"
API_KEY = "sk_live_51234567890abcdefgh"
DB_URL = "postgres://user:password123@db.example.com/db"

# ❌ MAUVAIS - Dans les commentaires
# Leon endpoint: https://leon.example.com?token=secret123
```

### 🔍 Avant chaque push: Audit sécurité

1. **Automatique (via git hook pre-push)**
  ```bash
  git push  # Le hook détecte les secrets et refuse le push
  ```

2. **Manuel: scanner les fichiers stagés**
  ```bash
  python3 scripts/audit-secrets.py --staged
  ```

3. **Manuel: scanner tout le code**
  ```bash
  python3 scripts/audit-secrets.py --dir src/
  ```

4. **Manuel: scan interactif avec suggestions**
  ```bash
  python3 scripts/audit-secrets.py --fix
  ```

### 🚨 Si un secret a été commité par erreur

1. **Ne pas ignorer!** Revenir immédiatement.

2. **Nettoyer localement**:
  ```bash
  git reset HEAD~1          # Annuler le commit (garder les changements)
  git rm --cached .env      # Retirer le fichier de git
  echo ".env" >> .gitignore # Ajouter à gitignore
  git commit -m "Remove secrets from tracked files (Fixes #SEC-001)"
  ```

3. **Rotation des credentials**:
  - Régénérer les tokens/API keys compromise
  - Notifier l'équipe (Slack sécurité)
  - Ajouter dans la checklist post-incident

4. **Audit historique**:
  ```bash
  git log --all --full-history -- .env  # Voir tous les commits qui ont touché .env
  ```

### 📊 Patterns détectés automatiquement

Le hook pre-push détecte:
- Clés privées (RSA, SSH, PEM)
- API keys (GitHub, Slack, AWS)
- Tokens (JWT, Bearer, Basic Auth)
- Database URLs avec credentials
- Fichiers protégés (.env, *.pem, secrets.json)

Faux positifs? Ajouter à `.secretsignore`:
```
# .secretsignore
docs/examples/**          # Exemples documentation
tests/fixtures/secrets.py # Données de test
```

### 🔗 Ressources

- [docs/bonnes-pratiques/03-securite-et-git.md](docs/bonnes-pratiques/03-securite-et-git.md)
- [scripts/audit-secrets.py](scripts/audit-secrets.py) — Scanner manuel
- [.git/hooks/pre-push](.git/hooks/pre-push) — Hook automatique

### 🎯 Checklist avant CHAQUE push

- [ ] `git diff --staged | grep -i "password\|secret\|token\|key"` ← Rien trouvé?
- [ ] `python3 scripts/audit-secrets.py --staged` ← Aucun problème?
- [ ] Vérifier `.env` et `*.pem` pas stagés: `git diff --cached --name-only | grep -E ".env|.pem|.key"`
- [ ] OUI à tout? → `git push` (le hook pre-push fera la vérification finale)

---

**Rappel**: Les secrets commités deviennent publiquement accessibles. L'historique Git ne les efface pas.
