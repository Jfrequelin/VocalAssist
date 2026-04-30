#!/bin/bash
# Script d'aide pour synchroniser les tickets GitHub

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/sync_tickets.py"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Vérifier que Python 3 est disponible
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 non trouvé${NC}"
    exit 1
fi

# Par défaut: sync des tickets ouverts
STATE="${1:-open}"
LABELS="${@:2}"

if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  GITHUB_TOKEN non configuré.${NC}"
    echo "   Production limité à 60 requêtes/heure au lieu de 5000."
    echo ""
    echo "   Pour configurer:"
    echo "     export GITHUB_TOKEN='votre_token_github'"
    echo ""
    read -p "   Continuer quand même ? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}🚀 Synchronisation des tickets...${NC}"
python3 "$PYTHON_SCRIPT" --state "$STATE" $LABELS

echo ""
echo -e "${GREEN}✅ Tickets synchronisés dans: doc/tickets/${NC}"
echo ""
echo "Pour consulter:"
echo "  cat doc/tickets/INDEX.md"
echo ""
echo "Pour filtrer par sprint:"
echo "  ./scripts/sync.sh all --label 'Sprint 2 weeks'"
