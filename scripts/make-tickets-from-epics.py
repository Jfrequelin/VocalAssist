#!/usr/bin/env python3
"""
Helper script: Générer des tickets GitHub à partir des épics.

Usage:
    python3 scripts/make-tickets-from-epics.py --epic EDGE
    python3 scripts/make-tickets-from-epics.py --all
"""

import re
import argparse
from pathlib import Path

# Epic metadata
EPICS = {
    "EDGE": {
        "file": "docs/03-delivery/epics/EDGE-firmware-esp32-s3.md",
        "label": "EDGE",
        "template": """
## 📋 {epic_name} - {subtitle}

{description}

### Acceptance Criteria
{acceptance}

### Tasks
{tasks}

### Estimation: {estimation}
### Priority: {priority}

---
See full epic: {epic_link}
""",
    },
    "SRV": {
        "file": "docs/03-delivery/epics/SRV-stc-tts-server.md",
        "label": "SRV",
    },
    "ORCH": {
        "file": "docs/03-delivery/epics/ORCH-orchestrator-local-first.md",
        "label": "ORCH",
    },
    "DOM": {
        "file": "docs/03-delivery/epics/DOM-home-assistant.md",
        "label": "DOM",
    },
    "OBS": {
        "file": "docs/03-delivery/epics/OBS-observability.md",
        "label": "OBS",
    },
}


def extract_epic_info(epic_file: str) -> dict:
    """Extract épic information from markdown file."""
    path = Path(epic_file)
    if not path.exists():
        print(f"⚠️  File not found: {epic_file}")
        return {}
    
    content = path.read_text(encoding="utf-8")
    
    # Extract title, estimation, priority
    title_match = re.search(r"^# (🟨|🟩|🟧|🟣|🔴) Epic (.+)$", content, re.MULTILINE)
    title = title_match.group(2) if title_match else "Unknown"
    
    estimation_match = re.search(r"\*\*Estimation\*\*:\s+(.+?\s+pt)", content)
    estimation = estimation_match.group(1) if estimation_match else "TBD"
    
    priority_match = re.search(r"\*\*Priority\*\*:\s+(.+)", content)
    priority = priority_match.group(1) if priority_match else "Medium"
    
    # Extract subtasks
    subtasks = []
    subtask_matches = re.finditer(r"^\*\*([A-Z]+-\d+)\*\*:\s+(.+)", content, re.MULTILINE)
    for match in subtask_matches:
        subtasks.append({
            "id": match.group(1),
            "title": match.group(2),
        })
    
    # Extract acceptance criteria
    acceptance_match = re.search(
        r"## 🎯 Critères d'acceptation\n\n(.*?)\n\n##", 
        content, 
        re.DOTALL
    )
    acceptance = acceptance_match.group(1) if acceptance_match else "TBD"
    
    return {
        "title": title,
        "estimation": estimation,
        "priority": priority,
        "subtasks": subtasks,
        "acceptance": acceptance,
        "file": epic_file,
    }


def format_github_issue(subtask: dict, epic_label: str, epic_title: str) -> str:
    """Format a subtask as a GitHub issue template."""
    return f"""## {subtask['id']}: {subtask['title']}

**Epic**: {epic_label} ({epic_title})

See full epic: docs/03-delivery/epics/

### Labels
- `{epic_label}`
- `Sprint 2 weeks`
- `Priority-1`

### Links
- [Epic: {epic_title}]({epic_label}.md)
"""


def main():
    parser = argparse.ArgumentParser(description="Generate GitHub tickets from épics")
    parser.add_argument("--epic", choices=list(EPICS.keys()), help="Specific epic")
    parser.add_argument("--all", action="store_true", help="All épics")
    parser.add_argument("--format", choices=["github", "markdown"], default="markdown", help="Output format")
    
    args = parser.parse_args()
    
    if args.all:
        epics_to_process = list(EPICS.keys())
    elif args.epic:
        epics_to_process = [args.epic]
    else:
        print("Usage: python3 scripts/make-tickets-from-epics.py --epic EDGE [--all]")
        print("\nAvailable épics:")
        for code, info in EPICS.items():
            print(f"  {code} → {info['file']}")
        return
    
    for epic_code in epics_to_process:
        epic_info = EPICS[epic_code]
        data = extract_epic_info(epic_info["file"])
        
        if not data:
            continue
        
        print(f"\n{'=' * 60}")
        print(f"📋 {epic_code}: {data['title']}")
        print(f"{'=' * 60}")
        print(f"Estimation: {data['estimation']}")
        print(f"Priority: {data['priority']}")
        print(f"\nSubtasks: {len(data['subtasks'])}")
        
        for subtask in data["subtasks"]:
            print(f"  ✓ {subtask['id']}: {subtask['title']}")
        
        if args.format == "github":
            print(f"\n💡 GitHub Issue Template:\n")
            for subtask in data["subtasks"]:
                print(format_github_issue(subtask, epic_code, data["title"]))
        
        print(f"\n🔗 Full epic: {epic_info['file']}")


if __name__ == "__main__":
    main()
