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
- Apres chaque modification de code, faire systematiquement une passe Pylance sur les fichiers touches.
- Apres chaque modification de code, executer systematiquement les tests les plus proches de la zone modifiee, puis elargir si necessaire.
- Verifier qu'un lancement local fonctionne apres modification.
- Mettre a jour la documentation lorsque le comportement change.

## Tickets GitHub et tickets locaux

- Synchroniser systematiquement les tickets GitHub et les tickets locaux avant et apres une mise a jour significative du suivi.
- Les tickets locaux doivent etre ecrits dans le repertoire separe doc/tickets, qui est ignore par Git.
- Ne jamais versionner les tickets locaux synchronises; seule la source GitHub fait foi.
- Si un script de synchronisation evolue, conserver ce chemin comme emplacement canonique des tickets locaux.

## Workflow obligatoire de traitement d'un ticket

Pour chaque ticket de developpement, suivre strictement cet ordre:

1. **Preparation TDD**: creer ou mettre a jour les tests avant le code metier.
2. **Implementation**: ecrire le code minimal necessaire pour faire passer les tests.
3. **Passe Pylance**: corriger toutes les erreurs et types inconnus sur les fichiers touches.
4. **Passe Pylint**: corriger les alertes pertinentes liees au ticket.
5. **Validation fonctionnelle**: executer les tests cibles puis les tests elargis si necessaire.
6. **Mise a jour Git**: commit et push avec reference explicite du ticket (`Fixes #<id>` quand applicable).
7. **Mise a jour du ticket**: documenter le resultat, puis passer le ticket a l'etat `ok` (fermeture ou commentaire de resolution selon workflow projet).

Raccourci interdit: ne pas sauter l'une de ces etapes, meme pour une correction mineure.

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

## Contrainte: Priorité aux Solutions Open Source

**Principe Directeur**: Utiliser des solutions open source pour tous les composants critiques du projet.

### ✅ Critères de Sélection

Quand choisir une dépendance:

1. **Préférence absolue: Open Source (MIT, Apache 2.0, GPL 3.0, etc.)**
   - Audit de sécurité possible
   - Pas de vendor lock-in
   - Support communautaire actif
   - Exemple: FastAPI, pytest, Piper TTS

2. **Acceptable: Dual licensing (open source + commercial)**
   - Ex: PostgreSQL, Redis
   - Mais version open source doit être viable en production

3. **À éviter: Propriétaire/Freemium**
   - Risque de dépendance
   - Coûts imprévisibles
   - Incompatible avec la philosophie du projet
   - Exception: évaluation temporaire (avec issue GitHub de limitation)

### 📚 Stack Open Source Recommandé

#### Backend/API
- **Framework**: FastAPI (MIT) - au lieu de propriétaire
- **ORM**: SQLAlchemy (MIT)
- **Task Queue**: Celery (BSD)
- **Cache**: Redis (BSD)
- **Database**: PostgreSQL (PostgreSQL License - like BSD)

#### Vocal/Audio
- **STT**: Faster-Whisper (MIT) - basé sur OpenAI Whisper
- **TTS**: Piper (MIT) - par rhasspy community
- **Wake Word**: PocketSphinx (BSD) ou Rhasspy
- **Audio I/O**: PyAudio, sounddevice, librosa (BSD/MIT)
- **Audio Processing**: SciPy, NumPy (BSD)

#### Firmware Embedded
- **Language**: Rust (MIT/Apache 2.0) - au lieu de C propriétaire
- **Build**: Cargo, CMake (MIT/BSD)
- **RTOS**: FreeRTOS (MIT) si besoin
- **HAL**: stm32l4xx-hal, stm32h7xx-hal (MIT/Apache)
- **Libraries**: cortex-m, embedded-hal ecosystem

#### Machine Learning
- **Framework**: PyTorch (BSD) ou scikit-learn (BSD)
- **Inference**: ONNX (MIT)
- **Quantization**: TensorRT alternatives open source

#### Infrastructure/DevOps
- **Container**: Docker (Moby - Apache 2.0)
- **Orchestration**: Kubernetes (Apache 2.0) si scaling
- **CI/CD**: GitHub Actions (free tier) ou Gitea Runners
- **Monitoring**: Prometheus + Grafana (Apache 2.0 + AGPL)
- **Logging**: ELK Stack variants open source

#### Frontend
- **Framework**: Vue.js / React / Svelte (MIT)
- **Design**: Bootstrap (MIT) ou Tailwind (MIT)
- **Charts**: Chart.js (MIT)

### 🚫 Dépendances Propriétaires à Remplacer

Si rencontré:

| Propriétaire | Alternative Open Source | Justification |
|--------------|--------------------------|---------------|
| Nuance Speech | Whisper + FastWhisper | Gratuit, meilleure qualité |
| Google TTS | Piper TTS | Embarquable, plus rapide |
| AWS Lambda | FaaS open source | Eviter vendor lock-in |
| Auth0 | Keycloak, Authentic. | Contrôle complet |
| Sendgrid | Postfix, Mailgun open | Réduction coûts |

### 📋 Checklist pour chaque dépendance

Avant d'ajouter une dépendance (pip, cargo, npm):

```bash
# 1. Vérifier licence
grep -i "license" /path/to/package/LICENSE
# ✅ MIT, Apache 2.0, BSD, GPL 3.0
# ❌ Propriétaire, Freemium, Cloud-only

# 2. Vérifier activité GitHub
gh repo view <owner>/<repo> --json updatedAt,stargazers,forks
# ✅ Dernière activité < 3 mois, 100+ stars
# ❌ Abandonné, activité < 1 an

# 3. Vérifier taille/overhead
# ❌ Dépendance unique qui impose 50+ transitive deps
# ✅ Capable fonctionnelle isolée

# 4. Vérifier sécurité
# pip-audit nom_package
# cargo audit (si Rust)
# npm audit (si JavaScript)
```

### 🔗 Ressources Open Source du Projet

**Core Components**:
- STM32 Firmware: Rust + cortex-m (MIT)
- Backend: FastAPI + PostgreSQL + SQLAlchemy (MIT/BSD)
- Audio: Whisper + Piper (MIT)
- Testing: pytest (MIT)
- Typing: Pylance + type stubs (MIT)

**Documentação**:
- [Open Source Initiative](https://opensource.org/licenses) - Liste des licences approuvées
- [SPDX License List](https://spdx.org/licenses/) - Identifiant standardisé
- [choosealicense.com](https://choosealicense.com/) - Guide choix licence

---

**Rappel**: Les secrets commités deviennent publiquement accessibles. L'historique Git ne les efface pas.
