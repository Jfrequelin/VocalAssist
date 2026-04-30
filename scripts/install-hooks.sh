#!/bin/bash
# Installation des git hooks personnalisés

set -e

HOOKS_DIR=".git/hooks"

echo "📦 Installation des git hooks..."

# Rendre exécutables
chmod +x "$HOOKS_DIR/pre-commit"
chmod +x "$HOOKS_DIR/pre-push"

echo "✅ Hooks installés:"
echo "  ✓ pre-commit: Vérification tickets & format"
echo "  ✓ pre-push: Détection de secrets"
echo ""
echo "Les hooks vérifieront:"
echo "  • Format de commit (fix/feat/refactor doivent référencer #XXX)"
echo "  • Pas d'accident .tickets-local/ commités"
echo "  • Absence de secrets/credentials avant push"
echo ""
echo "Pour désactiver temporairement:"
echo "  git commit --no-verify      # passer le pre-commit"
echo "  git push --no-verify        # passer le pre-push (⚠️ attention!)"

echo "✅ Hooks installés:"
echo "  ✓ pre-commit: Vérification tickets & format"
echo ""
echo "Les hooks vérifieront:"
echo "  • Format de commit (fix/feat/refactor doivent référencer #XXX)"
echo "  • Pas d'accident .tickets-local/ commités"
echo ""
echo "Pour désactiver temporairement:"
echo "  git commit --no-verify"
