from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WakeWordResult:
    """Résultat de l'extraction du wake word et de la commande."""

    activated: bool
    command: str | None = None
    is_help_requested: bool = False

    def format_for_display(self) -> str:
        """Formate le résultat pour affichage utilisateur."""
        if not self.activated:
            return ""

        if self.is_help_requested:
            return "Commandes disponibles: heure, date, meteo, lumiere, musique, rappel, agenda, aide, stop"

        if self.command:
            return self.command

        return ""


class WakeWordHandler:
    """Gestionnaire centralisé pour la détection du wake word et extraction de commande."""

    def __init__(self, wake_word: str = "nova") -> None:
        self.wake_word = wake_word.lower().strip()

    def extract_command(self, message: str) -> WakeWordResult:
        """Extrait la commande après le wake word.

        Returns:
            WakeWordResult avec:
            - activated: True si le wake word a été détecté en début de message
            - command: le texte après le wake word (None si vide ou uniquement "aide")
            - is_help_requested: True si le message est vide ou contient "aide"
        """
        lowered = message.lower().strip()

        if not lowered.startswith(self.wake_word):
            return WakeWordResult(activated=False)

        remainder = lowered[len(self.wake_word) :].strip()

        if not remainder:
            return WakeWordResult(activated=True, command=None, is_help_requested=True)

        if remainder == "aide" or remainder == "help":
            return WakeWordResult(activated=True, command=None, is_help_requested=True)

        normalized_command = " ".join(remainder.split())
        return WakeWordResult(activated=True, command=normalized_command, is_help_requested=False)
