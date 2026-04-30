#!/usr/bin/env python3
"""
Audit de sécurité: Détecter les secrets dans le code source.

Usage:
    python3 scripts/audit-secrets.py                    # Scan tous les fichiers
    python3 scripts/audit-secrets.py --staged           # Scan fichiers stagés seulement
    python3 scripts/audit-secrets.py --file src/foo.py  # Scan un fichier
    python3 scripts/audit-secrets.py --fix              # Interactif fix suggestions
"""

import re
import argparse
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional


class SecretScanner:
    """Scan pour détecter les secrets potentiels."""
    
    # Patterns de secrets
    PATTERNS = {
        "PRIVATE_KEY": r"-----BEGIN.*PRIVATE KEY-----",
        "API_KEY": r"(api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-zA-Z0-9\-._]{20,}",
        "AWS_KEY": r"(AKIA[0-9A-Z]{16}|aws[_-]?secret[_-]?access[_-]?key)",
        "GITHUB_TOKEN": r"gh[pousr]{1}_[a-zA-Z0-9_]{36,255}",
        "SLACK_TOKEN": r"xox[baprs]{1}-[0-9]{10,12}-[a-zA-Z0-9]{24,26}-[a-zA-Z0-9_\-]{50,}",
        "DATABASE_URL": r"(postgres|mysql|mongodb)://.*:.*@.*",
        "ENV_SECRET": r"^(PASSWORD|SECRET|TOKEN|KEY|CREDENTIAL)\s*=\s*[^\s]",
        "PEM_FILE": r"\.pem$|\.key$",
        "SSH_KEY": r"ssh-rsa\s+[A-Z0-9+/=]{10,}",
        "JWT": r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
        "BASIC_AUTH": r"Authorization:\s*Basic\s+[A-Za-z0-9+/=]{20,}",
    }
    
    # Dossiers à ignorer
    IGNORE_DIRS = {
        ".git", "__pycache__", ".venv", "node_modules", ".pytest_cache",
        ".tickets-local", "build", "dist", "*.egg-info"
    }
    
    def __init__(self, ignore_file: str = ".secretsignore"):
        self.ignore_file = Path(ignore_file)
        self.ignore_patterns = self._load_ignore_patterns()
    
    def _load_ignore_patterns(self) -> List[str]:
        """Charger les patterns d'ignore customisés."""
        if not self.ignore_file.exists():
            return []
        
        patterns = []
        for line in self.ignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
        
        return patterns
    
    def _should_ignore(self, filepath: str) -> bool:
        """Vérifier si le fichier doit être ignoré."""
        path = Path(filepath)
        
        # Ignorer les dossiers standards
        for part in path.parts:
            if part in self.IGNORE_DIRS or part.startswith("."):
                return True
        
        # Ignorer selon .secretsignore
        for pattern in self.ignore_patterns:
            if pattern.endswith("**"):
                # Pattern de dossier
                if pattern[:-2] in str(path):
                    return True
            elif path.match(pattern) or str(path).endswith(pattern):
                return True
        
        return False
    
    def scan_file(self, filepath: str) -> List[Tuple[int, str, str]]:
        """Scanner un fichier pour détecter les secrets.
        
        Returns:
            Liste de (line_num, pattern_name, line_content)
        """
        path = Path(filepath)
        if not path.exists():
            return []
        
        if self._should_ignore(filepath):
            return []
        
        findings = []
        
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        
        for line_num, line in enumerate(content.splitlines(), 1):
            # Skip commentaires
            if line.strip().startswith("#"):
                continue
            
            for pattern_name, pattern in self.PATTERNS.items():
                if re.search(pattern, line, re.IGNORECASE):
                    # Masquer les valeurs pour la sortie
                    masked_line = re.sub(r"(['\"])([^'\"]{10})[^'\"]*(['\"])", r"\1***\3", line)
                    findings.append((line_num, pattern_name, masked_line))
        
        return findings
    
    def scan_staged(self) -> List[Tuple[str, List[Tuple[int, str, str]]]]:
        """Scanner les fichiers stagés pour commit."""
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                check=True
            )
            staged_files = result.stdout.strip().split("\n")
        except subprocess.CalledProcessError:
            return []
        
        findings_by_file = []
        for filepath in staged_files:
            if filepath:
                findings = self.scan_file(filepath)
                if findings:
                    findings_by_file.append((filepath, findings))
        
        return findings_by_file
    
    def scan_directory(self, directory: str = ".") -> List[Tuple[str, List[Tuple[int, str, str]]]]:
        """Scanner un répertoire."""
        findings_by_file = []
        
        for filepath in Path(directory).rglob("*"):
            if filepath.is_file():
                findings = self.scan_file(str(filepath))
                if findings:
                    findings_by_file.append((str(filepath), findings))
        
        return findings_by_file


def main():
    parser = argparse.ArgumentParser(description="Détecter les secrets dans le code")
    parser.add_argument("--staged", action="store_true", help="Scanner fichiers stagés seulement")
    parser.add_argument("--file", help="Scanner un fichier spécifique")
    parser.add_argument("--dir", default=".", help="Scanner un répertoire (défaut: .)")
    parser.add_argument("--fix", action="store_true", help="Mode interactif fix")
    
    args = parser.parse_args()
    
    scanner = SecretScanner()
    
    # Déterminer ce qu'il faut scanner
    if args.file:
        findings = [(args.file, scanner.scan_file(args.file))]
    elif args.staged:
        findings = scanner.scan_staged()
    else:
        findings = scanner.scan_directory(args.dir)
    
    # Afficher les résultats
    if not findings:
        print("✅ Aucun secret détecté!")
        return 0
    
    print(f"❌ {sum(len(f) for _, f in findings)} secret(s) trouvé(s):\n")
    
    total_issues = 0
    for filepath, file_findings in findings:
        print(f"📄 {filepath}")
        for line_num, pattern_name, line_content in file_findings:
            print(f"   L{line_num}: [{pattern_name}] {line_content[:80]}")
            total_issues += 1
        print()
    
    if args.fix:
        print("\n🔧 Mode fix interactif:")
        for filepath, file_findings in findings:
            print(f"\n📝 Éditer {filepath}?")
            response = input("  (y)es / (s)kip / (i)gnore / (q)uit: ").lower()
            if response == "y":
                import subprocess
                subprocess.run(["vim", filepath])
            elif response == "i":
                # Ajouter à .secretsignore
                with open(".secretsignore", "a") as f:
                    f.write(f"\n{filepath}  # Added to ignore\n")
                print(f"  ✓ Ajouté à .secretsignore")
            elif response == "q":
                break
    
    return 1 if total_issues > 0 else 0


if __name__ == "__main__":
    exit(main())
