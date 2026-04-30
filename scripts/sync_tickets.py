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
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


class GitHubTicketSync:
    """Synchronise les tickets GitHub vers des fichiers markdown locaux."""
    
    GITHUB_API = "https://api.github.com"
    
    def __init__(self, owner: str, repo: str, token: Optional[str] = None):
        self.owner = owner
        self.repo = repo
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.output_dir = Path(".tickets-local")
        self.headers = self._build_headers()
        
        if not self.token:
            print("⚠️  Avertissement: GITHUB_TOKEN non configuré. Limité à 60 req/h (au lieu de 5000).")
    
    def _build_headers(self) -> Dict[str, str]:
        """Construit les headers pour l'API GitHub."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Effectue une requête GET à l'API GitHub."""
        url = f"{self.GITHUB_API}/repos/{self.owner}/{self.repo}/{endpoint}"
        all_results = []
        page = 1
        
        while True:
            query_params = params or {}
            query_params["page"] = page
            query_params["per_page"] = 100
            
            resp = requests.get(url, headers=self.headers, params=query_params)
            resp.raise_for_status()
            
            data = resp.json()
            if not data:
                break
            
            all_results.extend(data)
            page += 1
        
        return all_results
    
    def _format_ticket_markdown(self, issue: Dict[str, Any]) -> str:
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
        self.output_dir.mkdir(exist_ok=True)
        
        # Construire les paramètres de requête
        params = {"state": state}
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
        manifest = {
            "synced_at": datetime.now().isoformat(),
            "owner": self.owner,
            "repo": self.repo,
            "state": state,
            "labels": labels,
            "total_issues": len(issues),
            "created_files": created_count,
            "updated_files": updated_count,
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
    
    def _generate_index(self, issues: List[Dict[str, Any]]) -> str:
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
            labels_str = ' '.join([f"`{l['name']}`" for l in issue['labels']]) if issue['labels'] else ''
            index += f"- **[#{issue['number']}]({issue['number']:04d}-*.md)** {issue['title']} {labels_str}\n"
        
        index += f"\n## 🔴 Fermés ({len(closed_issues)})\n\n"
        for issue in closed_issues:
            labels_str = ' '.join([f"`{l['name']}`" for l in issue['labels']]) if issue['labels'] else ''
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
        print(f"\n✅ Synchronisation terminée!")
        print(f"   Créés: {results['created']}")
        print(f"   Mis à jour: {results['updated']}")
        print(f"   Total: {results['total']}")
        print(f"   Dossier: {sync.output_dir.absolute()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur API GitHub: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
