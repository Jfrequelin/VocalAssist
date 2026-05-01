#!/usr/bin/env python3
"""
Script de synchronisation des tickets GitHub vers fichiers markdown locaux.

Usage:
    python3 scripts/sync_tickets.py --owner Jfrequelin --repo VocalAssist --token <GITHUB_TOKEN>
    python3 scripts/sync_tickets.py --owner Jfrequelin --repo VocalAssist  # utilise GITHUB_TOKEN env var
    python3 scripts/sync_tickets.py --state open --label "Sprint 2 weeks"
"""

import os
import json
import argparse
import subprocess
import re
from pathlib import Path
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Optional, List, Dict, Any, TypedDict, cast


IssueData = Dict[str, Any]
QueryParams = Dict[str, str | int]


class IssueRef(TypedDict):
    number: int
    title: str
    state: str
    url: str


class MacroCounts(TypedDict):
    total: int
    open: int
    closed: int


class MacroEntry(TypedDict):
    macro_code: str
    issues: dict[str, list[IssueRef]]
    counts: MacroCounts


class MacroIssueMapping(TypedDict):
    generated_at: str
    owner: str
    repo: str
    macros: dict[str, MacroEntry]
    unmatched_issues: list[int]


class GitHubTicketSync:
    """Synchronise les tickets GitHub vers des fichiers markdown locaux."""

    GITHUB_API = "https://api.github.com"
    ISSUE_KINDS = ["macro", "task", "subticket", "atomic-task", "other"]

    def __init__(self, owner: str, repo: str, token: Optional[str] = None):
        self.owner = owner
        self.repo = repo
        self.token = token or os.getenv("GITHUB_TOKEN") or self._load_gh_token()
        self.output_dir = Path("doc/tickets")
        self.headers = self._build_headers()

        if not self.token:
            print("⚠️  Avertissement: aucun token GitHub detecte. Limite a 60 req/h (au lieu de 5000).")

    def _load_gh_token(self) -> Optional[str]:
        """Recupere le token de gh si l'utilisateur est deja authentifie."""
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None

        token = result.stdout.strip()
        return token or None

    def _build_headers(self) -> Dict[str, str]:
        """Construit les headers pour l'API GitHub."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _get(self, endpoint: str, params: Optional[QueryParams] = None) -> List[IssueData]:
        """Effectue une requête GET à l'API GitHub."""
        all_results: List[IssueData] = []
        page = 1

        while True:
            query_params: QueryParams = dict(params or {})
            query_params["page"] = page
            query_params["per_page"] = 100

            query_string = urlencode(query_params)
            url = f"{self.GITHUB_API}/repos/{self.owner}/{self.repo}/{endpoint}?{query_string}"
            request = Request(url, headers=self.headers, method="GET")

            with urlopen(request) as response:
                response_body = response.read().decode("utf-8")

            data = cast(List[IssueData], json.loads(response_body))
            if not data:
                break

            all_results.extend(data)
            page += 1

        return all_results

    def _format_ticket_markdown(self, issue: IssueData) -> str:
        """Formate une issue GitHub en markdown."""
        template = f"""# [{issue['number']}] {issue['title']}

**État**: {issue['state']}
**Créé**: {issue['created_at']}
**Mis à jour**: {issue['updated_at']}
**Assigné à**: {issue['assignee']['login'] if issue['assignee'] else 'Non assigné'}

## Labels
{', '.join([f"`{label['name']}`" for label in issue['labels']]) if issue['labels'] else 'Aucun'}

## Milestone
{issue['milestone']['title'] if issue['milestone'] else 'Aucun'}

## Description

{issue['body'] or '*(Pas de description)*'}

## Métadonnées JSON

```json
{{
  "number": {issue['number']},
  "id": {issue['id']},
  "url": "{issue['html_url']}",
  "state": "{issue['state']}",
  "created_at": "{issue['created_at']}",
  "updated_at": "{issue['updated_at']}",
  "closed_at": {json.dumps(issue['closed_at'])},
  "comments": {issue['comments']}
}}
```

---
*Fichier synchronisé automatiquement: {datetime.now().isoformat()}*
*Ne pas modifier manuellement (changements perdus à la prochaine sync)*
"""
        return template.strip()

    def sync(self, state: str = "open", labels: Optional[List[str]] = None) -> Dict[str, int]:
        """Synchronise les tickets vers le dossier local."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Construire les paramètres de requête
        params: QueryParams = {"state": state}
        if labels:
            params["labels"] = ",".join(labels)

        print(f"📡 Récupération des tickets: state={state}, labels={labels or 'tous'}")
        issues = self._get("issues", params)

        print(f"✅ {len(issues)} ticket(s) trouvé(s)")

        # Créer les fichiers de tickets
        created_count = 0
        updated_count = 0

        for issue in issues:
            filename = f"{issue['number']:04d}-{issue['title'][:50].replace('/', '-').replace(' ', '_')}.md"
            filepath = self.output_dir / filename

            content = self._format_ticket_markdown(issue)

            if filepath.exists():
                updated_count += 1
                print(f"  ♻️  #{issue['number']} - {issue['title'][:50]}")
            else:
                created_count += 1
                print(f"  ✨ #{issue['number']} - {issue['title'][:50]}")

            filepath.write_text(content, encoding="utf-8")

        # Créer un index
        index_content = self._generate_index(issues)
        (self.output_dir / "INDEX.md").write_text(index_content, encoding="utf-8")

        # Créer un manifeste
        mapping = self.build_macro_issue_mapping(issues)
        (self.output_dir / "macro_issue_mapping.json").write_text(
            json.dumps(mapping, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.output_dir / "MACRO-ISSUE-MAPPING.md").write_text(
            self._generate_mapping_markdown(mapping),
            encoding="utf-8",
        )

        manifest: Dict[str, Any] = {
            "synced_at": datetime.now().isoformat(),
            "owner": self.owner,
            "repo": self.repo,
            "state": state,
            "labels": labels,
            "total_issues": len(issues),
            "created_files": created_count,
            "updated_files": updated_count,
            "mapping_file": "macro_issue_mapping.json",
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8"
        )

        return {
            "created": created_count,
            "updated": updated_count,
            "total": len(issues),
        }

    def _extract_macro_code(self, issue: IssueData) -> Optional[str]:
        for label in issue.get("labels", []):
            name = str(label.get("name", ""))
            if re.fullmatch(r"macro-\d{3}", name):
                return name.upper().replace("-", "-")

        title = str(issue.get("title", ""))
        match = re.search(r"MACRO-(\d{3})", title)
        if match:
            return f"MACRO-{match.group(1)}"
        return None

    def _classify_issue_kind(self, issue: IssueData) -> str:
        label_names = {str(label.get("name", "")) for label in issue.get("labels", [])}
        if "macro" in label_names:
            return "macro"
        if "task" in label_names:
            return "task"
        if "subticket" in label_names:
            return "subticket"
        if "atomic-task" in label_names:
            return "atomic-task"
        return "other"

    def build_macro_issue_mapping(self, issues: List[IssueData]) -> MacroIssueMapping:
        macros: dict[str, MacroEntry] = {}
        unmatched: List[int] = []

        for issue in issues:
            number = int(issue.get("number", 0))
            title = str(issue.get("title", ""))
            state = str(issue.get("state", "open"))
            kind = self._classify_issue_kind(issue)
            macro_code = self._extract_macro_code(issue)

            if not macro_code:
                unmatched.append(number)
                continue

            macro_entry: MacroEntry = macros.setdefault(
                macro_code,
                {
                    "macro_code": macro_code,
                    "issues": {
                        "macro": [],
                        "task": [],
                        "subticket": [],
                        "atomic-task": [],
                        "other": [],
                    },
                    "counts": {
                        "total": 0,
                        "open": 0,
                        "closed": 0,
                    },
                },
            )

            issue_info: IssueRef = {
                "number": number,
                "title": title,
                "state": state,
                "url": str(issue.get("html_url", "")),
            }
            macro_entry["issues"][kind].append(issue_info)
            macro_entry["counts"]["total"] += 1
            if state == "open":
                macro_entry["counts"]["open"] += 1
            elif state == "closed":
                macro_entry["counts"]["closed"] += 1

        for macro_entry in macros.values():
            for kind in self.ISSUE_KINDS:
                bucket = macro_entry["issues"][kind]
                bucket.sort(key=lambda item: item["number"])

        return {
            "generated_at": datetime.now().isoformat(),
            "owner": self.owner,
            "repo": self.repo,
            "macros": dict(sorted(macros.items())),
            "unmatched_issues": sorted(unmatched),
        }

    def _generate_mapping_markdown(self, mapping: MacroIssueMapping) -> str:
        lines = [
            "# Mapping Macro -> Issues GitHub",
            "",
            f"**Synchronisé**: {mapping['generated_at']}",
            f"**Repo**: {mapping['owner']}/{mapping['repo']}",
            "",
        ]

        for macro_code, data in mapping["macros"].items():
            counts = data["counts"]
            lines.extend(
                [
                    f"## {macro_code}",
                    "",
                    f"- Total: {counts['total']}",
                    f"- Ouvert: {counts['open']}",
                    f"- Fermé: {counts['closed']}",
                    "",
                ]
            )
            for kind in self.ISSUE_KINDS:
                bucket = data["issues"][kind]
                if not bucket:
                    continue
                lines.append(f"### {kind}")
                lines.append("")
                for issue in bucket:
                    lines.append(
                        f"- #{issue['number']} ({issue['state']}) {issue['title']}"
                    )
                lines.append("")

        if mapping["unmatched_issues"]:
            lines.append("## Issues sans macro détectée")
            lines.append("")
            lines.append(", ".join(f"#{number}" for number in mapping["unmatched_issues"]))

        return "\n".join(lines).strip() + "\n"

    def _generate_index(self, issues: List[IssueData]) -> str:
        """Génère un index markdown des tickets."""
        # Trier par statut et numéro
        open_issues = sorted([i for i in issues if i['state'] == 'open'], key=lambda x: x['number'])
        closed_issues = sorted([i for i in issues if i['state'] == 'closed'], key=lambda x: x['number'])

        index = f"""# Index des Tickets

**Synchronisé**: {datetime.now().isoformat()}
**Total**: {len(issues)} ticket(s)
**Ouvert**: {len(open_issues)} | **Fermé**: {len(closed_issues)}

---

## 🟢 Ouverts ({len(open_issues)})

"""
        for issue in open_issues:
            labels_str = ' '.join([f"`{label['name']}`" for label in issue['labels']]) if issue['labels'] else ''
            index += f"- **[#{issue['number']}]({issue['number']:04d}-*.md)** {issue['title']} {labels_str}\n"

        index += f"\n## 🔴 Fermés ({len(closed_issues)})\n\n"
        for issue in closed_issues:
            labels_str = ' '.join([f"`{label['name']}`" for label in issue['labels']]) if issue['labels'] else ''
            index += f"- **[#{issue['number']}]({issue['number']:04d}-*.md)** {issue['title']} {labels_str}\n"

        return index


def main():
    parser = argparse.ArgumentParser(
        description="Synchronise les tickets GitHub vers fichiers markdown locaux"
    )
    parser.add_argument("--owner", default="Jfrequelin", help="Propriétaire du repo")
    parser.add_argument("--repo", default="VocalAssist", help="Nom du repo")
    parser.add_argument("--token", help="Token GitHub (défaut: GITHUB_TOKEN env var)")
    parser.add_argument("--state", default="open", choices=["open", "closed", "all"], help="État des tickets")
    parser.add_argument("--label", action="append", dest="labels", help="Filtrer par label (répétable)")

    args = parser.parse_args()

    sync = GitHubTicketSync(args.owner, args.repo, args.token)

    try:
        results = sync.sync(state=args.state, labels=args.labels)
        print("\n✅ Synchronisation terminée!")
        print(f"   Créés: {results['created']}")
        print(f"   Mis à jour: {results['updated']}")
        print(f"   Total: {results['total']}")
        print(f"   Dossier: {sync.output_dir.absolute()}")
    except (HTTPError, URLError) as e:
        print(f"❌ Erreur API GitHub: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
