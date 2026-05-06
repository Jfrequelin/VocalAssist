#!/usr/bin/env bash
# ─── install-deps.sh ─────────────────────────────────────────────────────────
# Installe les dépendances Python du serveur pont HA.
# Usage : ./scripts/install-deps.sh [--venv]
#
# Options :
#   --venv    Crée un virtualenv .venv/ avant d'installer (recommandé)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="$SCRIPT_DIR/requirements.txt"

USE_VENV=false
for arg in "$@"; do
  [[ "$arg" == "--venv" ]] && USE_VENV=true
done

# ── Virtualenv ────────────────────────────────────────────────────────────────
if $USE_VENV; then
  VENV_DIR="$SCRIPT_DIR/../.venv"
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Création du virtualenv dans .venv/ …"
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
  echo "Virtualenv activé : $VENV_DIR"
fi

# ── Installation ──────────────────────────────────────────────────────────────
echo "Installation des dépendances depuis $REQ_FILE …"
pip install --upgrade pip
pip install -r "$REQ_FILE"

echo ""
echo "✔ Dépendances installées."
echo ""
echo "Étapes suivantes :"
echo "  1. Démarrer la stack HA :"
echo "       cd docker && docker compose up -d"
echo ""
echo "  2. Configurer HA (première fois uniquement) :"
echo "       http://localhost:8123  → créer compte admin"
echo "       Paramètres → Intégrations → ajouter Wyoming Protocol"
echo "       Paramètres → Voix → Assistants → Whisper (STT) + Piper (TTS)"
echo "       Profil → Sécurité → créer un jeton d'accès longue durée"
echo ""
echo "  3. Créer le fichier .env :"
echo "       cp .env.example .env"
echo "       # puis renseigner HA_TOKEN=..."
echo ""
echo "  4. Démarrer le serveur pont :"
echo "       python3 scripts/server.py"
