from __future__ import annotations


class SystemMessages:
    """Catalogue centralisé des messages système pour uniformité terminal/vocal."""

    # Messages d'activation/wake word
    WAKE_WORD_MISSING = "mot cle absent, commande ignoree."
    COMMAND_EMPTY = "commande vide apres le mot cle."
    HELP_REQUEST = "intents supportes -> heure, date, meteo, musique, lumiere, rappel, agenda, stop"
    LEON_FALLBACK_ACTIVE = "fallback Leon actif si intent inconnu."

    # Messages Leon
    LEON_RESPONSE_SOURCE = "reponse fournie par Leon"
    LEON_UNAVAILABLE = "Leon indisponible, fallback local impossible"

    # Messages STT/TTS
    STT_ENGINE_FALLBACK = "STT reel indisponible, fallback mock"
    TTS_ENGINE_FALLBACK = "TTS reel indisponible, fallback mock"
    TTS_PIPER_PATH_MISSING = "PIPER_MODEL_PATH absent, fallback TTS mock"
    TTS_ERROR_FALLBACK = "TTS reel en erreur, fallback texte"

    @staticmethod
    def format_help_message() -> str:
        """Formate le message d'aide complet."""
        return f"{SystemMessages.HELP_REQUEST}\n{SystemMessages.LEON_FALLBACK_ACTIVE}"

    @staticmethod
    def format_trace(correlation_id: str, source: str) -> str:
        """Formate le message de trace."""
        return f"cid={correlation_id} source={source}"

    @staticmethod
    def format_stt_error(error: Exception) -> str:
        """Formate le message d'erreur STT avec raison."""
        return f"STT reel indisponible ({error}), fallback mock"

    @staticmethod
    def format_tts_error(error: Exception) -> str:
        """Formate le message d'erreur TTS avec raison."""
        return f"TTS reel en erreur ({error}), fallback texte"
