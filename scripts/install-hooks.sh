#!/bin/bash
# Installation des git hooks personnalisés

set -e

HOOKS_DIR=".git/hooks"

echo "📦 Installation des git hooks..."

# Rendre exécutable
chmod +x "$HOOKS_DIR/pre-commit"

echo "✅ Hooks installés:"
echo "  ✓ pre-commit: Vérification tickets & format"
echo ""
echo "Les hooks vérifieront:"
echo "  • Format de commit (fix/feat/refactor doivent référencer #XXX)"
echo "  • Pas d'accident .tickets-local/ commités"
echo ""
echo "Pour désactiver temporairement:"
echo "  git commit --no-verify"
