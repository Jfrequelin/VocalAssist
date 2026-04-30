#!/bin/bash
# Authentification GitHub CLI sans afficher le token

set -euo pipefail

show_help() {
    cat <<'EOF'
Usage:
  ./scripts/gh-auth-secure.sh --web
  ./scripts/gh-auth-secure.sh --token

Options:
  --web    Authentification GitHub via navigateur/device flow (recommande)
  --token  Saisie masquee d'un token personnel pour gh auth login --with-token
  --help   Afficher cette aide
EOF
}

if ! command -v gh >/dev/null 2>&1; then
    echo "❌ gh n'est pas installe"
    exit 1
fi

mode="${1:---web}"

case "$mode" in
    --web)
        echo "🔐 Lancement de l'authentification GitHub via navigateur"
        gh auth login --hostname github.com --git-protocol https --web
        ;;
    --token)
        echo "🔐 Saisissez votre token GitHub (saisie masquee, rien ne sera affiche)"
        read -r -s -p "GH token: " token
        echo
        if [[ -z "$token" ]]; then
            echo "❌ Token vide"
            exit 1
        fi
        printf '%s' "$token" | gh auth login --hostname github.com --git-protocol https --with-token
        unset token
        ;;
    --help|-h)
        show_help
        ;;
    *)
        echo "❌ Option inconnue: $mode"
        show_help
        exit 1
        ;;
esac

echo "✅ Etat auth gh"
gh auth status
