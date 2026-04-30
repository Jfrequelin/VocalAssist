#!/usr/bin/env python3
"""Publie les tickets macro et sous-tickets locaux vers GitHub via gh.

Usage:
    python3 scripts/publish_backlog_to_github.py --repo Jfrequelin/VocalAssist --macros
    python3 scripts/publish_backlog_to_github.py --repo Jfrequelin/VocalAssist --subtickets
    python3 scripts/publish_backlog_to_github.py --repo Jfrequelin/VocalAssist --all
    python3 scripts/publish_backlog_to_github.py --repo Jfrequelin/VocalAssist --all --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable, TypedDict

REPO_DEFAULT = "Jfrequelin/VocalAssist"
MACRO_DIR = Path("doc/tickets")
SUBTICKET_DIR = Path("doc/tickets/subtickets")


class PublishError(RuntimeError):
    pass


class ParsedSubtask(TypedDict):
    macro_id: str
    code: str
    title: str
    body: str
    priority: str
    objective: str
    deliverables: list[str]
    acceptance: list[str]


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=check)


def ensure_gh_ready() -> None:
    try:
        run_gh(["gh", "auth", "status"])
    except subprocess.CalledProcessError as exc:
        raise PublishError(
            "gh n'est pas authentifie. Lancez ./scripts/gh-auth-secure.sh --web puis relancez."
        ) from exc


def read_ticket_files(directory: Path, prefix: str) -> list[Path]:
    return sorted(
        path
        for path in directory.glob(f"{prefix}*.md")
        if path.is_file() and path.name not in {"MACRO-INDEX.md", "SUBTICKETS-INDEX.md"}
    )


def load_issue_index(repo: str) -> dict[str, int]:
    result = run_gh(
        ["gh", "issue", "list", "-R", repo, "--limit", "200", "--state", "all", "--json", "number,title"]
    )
    issues = json.loads(result.stdout)
    return {str(issue["title"]): int(issue["number"]) for issue in issues}


def parse_title_and_body(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise PublishError(f"Titre invalide dans {path}")
    title = lines[0][2:].strip()
    body = "\n".join(lines[1:]).strip()
    return title, body


def parse_subtasks(path: Path) -> list[ParsedSubtask]:
    content = path.read_text(encoding="utf-8")
    macro_match = re.search(r"MACRO-(\d{3})", content)
    if not macro_match:
        raise PublishError(f"Macro introuvable dans {path}")

    macro_id = macro_match.group(1)
    sections = re.split(r"(?m)^## ", content)
    subtasks: list[ParsedSubtask] = []
    for section in sections[1:]:
        lines = section.strip().splitlines()
        if not lines:
            continue
        title_line = lines[0].strip()
        task_match = re.match(r"(MACRO-\d{3}-T\d+) - (.+)", title_line)
        if not task_match:
            continue

        priority = ""
        objective = ""
        deliverables: list[str] = []
        acceptance: list[str] = []
        mode = ""
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("Priorite:"):
                priority = stripped.removeprefix("Priorite:").strip()
                mode = ""
            elif stripped.startswith("Objectif:"):
                objective = stripped.removeprefix("Objectif:").strip()
                mode = ""
            elif stripped.startswith("Livrables:"):
                mode = "deliverables"
            elif stripped.startswith("Critères d'acceptation:"):
                mode = "acceptance"
            elif stripped.startswith("- "):
                value = stripped[2:].strip()
                if mode == "deliverables":
                    deliverables.append(value)
                elif mode == "acceptance":
                    acceptance.append(value)

        subtasks.append(
            {
                "macro_id": macro_id,
                "code": task_match.group(1),
                "title": task_match.group(2).strip(),
                "body": "\n".join(lines[1:]).strip(),
                "priority": priority,
                "objective": objective,
                "deliverables": deliverables,
                "acceptance": acceptance,
            }
        )

    return subtasks


def issue_exists(repo: str, title: str) -> bool:
    result = run_gh(
        ["gh", "issue", "list", "-R", repo, "--search", f'in:title "{title}"', "--limit", "20", "--state", "all"],
        check=False,
    )
    if result.returncode != 0:
        return False
    return title in result.stdout


def ensure_labels(repo: str, labels: Iterable[str], dry_run: bool) -> None:
    for label in labels:
        if dry_run:
            print(f"[dry-run] ensure label: {label}")
            continue
        result = run_gh(["gh", "label", "create", label, "-R", repo], check=False)
        if result.returncode not in (0, 1):
            raise PublishError(result.stderr.strip() or f"Impossible de creer le label {label}")


def labels_for_macro(path: Path) -> list[str]:
    macro_id = path.stem.split("-")[1]
    return ["macro", f"macro-{macro_id}"]


def labels_for_subticket(path: Path) -> list[str]:
    macro_id = path.stem.split("-")[1]
    return ["subticket", f"macro-{macro_id}"]


def publish_issue(repo: str, path: Path, labels: list[str], dry_run: bool) -> None:
    title, body = parse_title_and_body(path)
    if issue_exists(repo, title):
        print(f"skip existing: {title}")
        return

    if dry_run:
        print(f"[dry-run] create issue: {title} labels={','.join(labels)} from={path}")
        return

    command = [
        "gh",
        "issue",
        "create",
        "-R",
        repo,
        "--title",
        title,
        "--body",
        body,
    ]
    for label in labels:
        command.extend(["--label", label])

    result = run_gh(command, check=False)
    if result.returncode != 0:
        raise PublishError(result.stderr.strip() or f"Creation issue echouee pour {title}")

    print(f"created: {title}")


def publish_direct_issue(repo: str, title: str, body: str, labels: list[str], dry_run: bool) -> None:
    if issue_exists(repo, title):
        print(f"skip existing: {title}")
        return

    if dry_run:
        print(f"[dry-run] create issue: {title} labels={','.join(labels)}")
        return

    command = [
        "gh",
        "issue",
        "create",
        "-R",
        repo,
        "--title",
        title,
        "--body",
        body,
    ]
    for label in labels:
        command.extend(["--label", label])

    result = run_gh(command, check=False)
    if result.returncode != 0:
        raise PublishError(result.stderr.strip() or f"Creation issue echouee pour {title}")

    print(f"created: {title}")


def publish_group(repo: str, files: list[Path], is_macro: bool, dry_run: bool) -> None:
    labels = {label for path in files for label in (labels_for_macro(path) if is_macro else labels_for_subticket(path))}
    ensure_labels(repo, sorted(labels | ({"macro"} if is_macro else {"subticket"})), dry_run)

    for path in files:
        path_labels = labels_for_macro(path) if is_macro else labels_for_subticket(path)
        publish_issue(repo, path, path_labels, dry_run)


def find_macro_title(issue_index: dict[str, int], macro_id: str) -> tuple[str, int]:
    prefix = f"MACRO-{macro_id} - "
    for title, number in issue_index.items():
        if title.startswith(prefix):
            return title, number
    raise PublishError(f"Issue macro introuvable pour MACRO-{macro_id}")


def publish_exploded_subtickets(repo: str, files: list[Path], dry_run: bool) -> None:
    labels = {"task"}
    for path in files:
        macro_id = path.stem.split("-")[1]
        labels.add(f"macro-{macro_id}")
    ensure_labels(repo, sorted(labels), dry_run)

    issue_index = load_issue_index(repo) if not dry_run else {}

    for path in files:
        parent_title, _ = parse_title_and_body(path)
        subtasks = parse_subtasks(path)
        parent_number = issue_index.get(parent_title)
        macro_title, macro_number = find_macro_title(issue_index, subtasks[0]["macro_id"]) if subtasks and not dry_run else (f"MACRO-{path.stem.split('-')[1]}", 0)

        for subtask in subtasks:
            title = f"{subtask['code']} - {subtask['title']}"
            references: list[str] = []
            if macro_number:
                references.append(f"Macro parente: #{macro_number} - {macro_title}")
            if parent_number:
                references.append(f"Ticket de decomposition parent: #{parent_number} - {parent_title}")

            reference_block = "\n".join(f"- {reference}" for reference in references)
            body = subtask["body"]
            if reference_block:
                body = f"## References\n{reference_block}\n\n{body}"

            publish_direct_issue(
                repo,
                title,
                body,
                ["task", f"macro-{subtask['macro_id']}"] ,
                dry_run,
            )


def build_atomic_title(code: str, index: int, text: str) -> str:
    label = f"S{index}"
    cleaned = text[0].upper() + text[1:] if text else f"Sous-tache {label}"
    return f"{code}-{label} - {cleaned}"


def publish_atomic_tasks(repo: str, files: list[Path], dry_run: bool) -> None:
    labels = {"atomic-task"}
    for path in files:
        macro_id = path.stem.split("-")[1]
        labels.add(f"macro-{macro_id}")
    ensure_labels(repo, sorted(labels), dry_run)

    issue_index = load_issue_index(repo) if not dry_run else {}

    for path in files:
        group_title, _ = parse_title_and_body(path)
        group_number = issue_index.get(group_title)
        parsed_subtasks = parse_subtasks(path)

        for parsed in parsed_subtasks:
            task_title = f"{parsed['code']} - {parsed['title']}"
            task_number = issue_index.get(task_title)
            macro_title, macro_number = find_macro_title(issue_index, parsed["macro_id"]) if not dry_run else (f"MACRO-{parsed['macro_id']}", 0)

            atomic_items: list[tuple[str, str]] = []
            for deliverable in parsed["deliverables"]:
                atomic_items.append((deliverable, "deliverable"))
            if parsed["acceptance"]:
                atomic_items.append(("Valider les criteres d'acceptation et les tests associes", "validation"))

            for idx, (item_text, item_kind) in enumerate(atomic_items, start=1):
                title = build_atomic_title(parsed["code"], idx, item_text)
                references: list[str] = []
                if macro_number:
                    references.append(f"Macro parente: #{macro_number} - {macro_title}")
                if group_number:
                    references.append(f"Ticket de decomposition parent: #{group_number} - {group_title}")
                if task_number:
                    references.append(f"Ticket parent: #{task_number} - {task_title}")

                body_lines = [
                    "## References",
                    *[f"- {reference}" for reference in references],
                    "",
                    f"Priorite: {parsed['priority'] or 'A definir'}",
                    f"Objectif parent: {parsed['objective'] or parsed['title']}",
                    f"Type: {'Livrable' if item_kind == 'deliverable' else 'Validation'}",
                    "",
                    "## Portee",
                    f"- {item_text}",
                ]

                if item_kind == "validation" and parsed["acceptance"]:
                    body_lines.extend([
                        "",
                        "## Criteres a couvrir",
                        *[f"- {criterion}" for criterion in parsed["acceptance"]],
                    ])

                publish_direct_issue(
                    repo,
                    title,
                    "\n".join(body_lines).strip(),
                    ["atomic-task", f"macro-{parsed['macro_id']}"],
                    dry_run,
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Publier backlog local vers GitHub")
    parser.add_argument("--repo", default=REPO_DEFAULT, help="Depot GitHub owner/repo")
    parser.add_argument("--macros", action="store_true", help="Publier seulement les macros")
    parser.add_argument("--subtickets", action="store_true", help="Publier seulement les sous-tickets")
    parser.add_argument("--explode-subtickets", action="store_true", help="Creer une issue GitHub par T1/T2/T3/T4")
    parser.add_argument("--explode-tasks", action="store_true", help="Creer une issue atomique par livrable et validation des tickets T")
    parser.add_argument("--all", action="store_true", help="Publier macros et sous-tickets")
    parser.add_argument("--dry-run", action="store_true", help="Afficher sans creer")
    args = parser.parse_args()

    if not (args.macros or args.subtickets or args.explode_subtickets or args.explode_tasks or args.all):
        parser.error("Choisissez --macros, --subtickets, --explode-subtickets, --explode-tasks ou --all")

    ensure_gh_ready()

    if args.macros or args.all:
        macro_files = read_ticket_files(MACRO_DIR, "MACRO-")
        publish_group(args.repo, macro_files, is_macro=True, dry_run=args.dry_run)

    if args.subtickets or args.all:
        subticket_files = read_ticket_files(SUBTICKET_DIR, "MACRO-")
        publish_group(args.repo, subticket_files, is_macro=False, dry_run=args.dry_run)

    if args.explode_subtickets:
        subticket_files = read_ticket_files(SUBTICKET_DIR, "MACRO-")
        publish_exploded_subtickets(args.repo, subticket_files, dry_run=args.dry_run)

    if args.explode_tasks:
        subticket_files = read_ticket_files(SUBTICKET_DIR, "MACRO-")
        publish_atomic_tasks(args.repo, subticket_files, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
