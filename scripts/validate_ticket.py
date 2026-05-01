#!/usr/bin/env python3
"""Runner de validation standard pour le traitement d'un ticket.

Workflow applique:
1. Compilation Python ciblee (equivalent garde-fou syntaxe)
2. Tests cibles (ou suite unittest par defaut)
3. Passe Pylance via pyright si disponible
4. Passe pylint
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ValidationStep:
    """Represente une etape de validation executable."""

    name: str
    command: list[str]


def build_plan(
    files: list[str],
    tests: list[str],
    has_pyright: bool,
    has_pylint: bool,
    pylint_fail_under: float,
) -> list[ValidationStep]:
    """Construit le plan de validation en fonction des outils disponibles."""

    if not files:
        raise ValueError("Au moins un fichier doit etre fourni via --files")

    plan: list[ValidationStep] = [
        ValidationStep(name="py_compile", command=["python3", "-m", "py_compile", *files]),
    ]

    if tests:
        plan.append(
            ValidationStep(name="tests", command=["python3", "-m", "unittest", *tests])
        )
    else:
        plan.append(ValidationStep(name="tests", command=["python3", "-m", "unittest"]))

    if has_pyright:
        plan.append(ValidationStep(name="pyright", command=["pyright", *files]))

    if has_pylint:
        fail_under_arg = f"--fail-under={pylint_fail_under:g}"
        pylint_command = ["python3", "-m", "pylint"]
        pylint_command.append(fail_under_arg)
        pylint_command.extend(files)
        plan.append(
            ValidationStep(
                name="pylint",
                command=pylint_command,
            )
        )

    return plan


def _run_step(step: ValidationStep, dry_run: bool) -> int:
    """Execute une etape de validation et retourne son code de sortie."""

    print(f"[validate] {step.name}: {' '.join(step.command)}")
    if dry_run:
        return 0

    result = subprocess.run(step.command, check=False)
    return result.returncode


def main() -> int:
    """Point d'entree CLI du runner de validation."""

    parser = argparse.ArgumentParser(description="Validation standard d'un ticket")
    parser.add_argument("--files", nargs="+", required=True, help="Fichiers modifies")
    parser.add_argument("--tests", nargs="*", default=[], help="Tests cibles a executer")
    parser.add_argument("--strict-pylance", action="store_true", help="Echoue si pyright indisponible")
    parser.add_argument("--strict-pylint", action="store_true", help="Echoue si pylint indisponible")
    parser.add_argument(
        "--pylint-fail-under",
        type=float,
        default=9.0,
        help="Score minimal pylint requis (par defaut: 9.0)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Affiche les commandes sans executer")
    args = parser.parse_args()

    has_pyright = shutil.which("pyright") is not None
    has_pylint = True
    probe = subprocess.run(["python3", "-m", "pylint", "--version"], check=False, capture_output=True)
    if probe.returncode != 0:
        has_pylint = False

    if args.strict_pylance and not has_pyright:
        print("[validate] erreur: pyright indisponible pour la passe Pylance")
        return 2

    if args.strict_pylint and not has_pylint:
        print("[validate] erreur: pylint indisponible")
        return 3

    if not has_pyright:
        print("[validate] info: pyright indisponible, passe Pylance a faire dans VS Code")
    if not has_pylint:
        print("[validate] info: pylint indisponible, installez-le pour une passe complete")

    plan = build_plan(
        files=args.files,
        tests=args.tests,
        has_pyright=has_pyright,
        has_pylint=has_pylint,
        pylint_fail_under=args.pylint_fail_under,
    )

    for step in plan:
        rc = _run_step(step, dry_run=args.dry_run)
        if rc != 0:
            print(f"[validate] echec sur {step.name} (code {rc})")
            return rc

    print("[validate] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
