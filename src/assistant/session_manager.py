from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from uuid import uuid4


class SessionState(Enum):
    """États possibles d'une session."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CLOSED = "closed"


@dataclass
class Session:
    """Représente une session utilisateur."""

    session_id: str
    state: SessionState
    started_at: float
    last_activity_at: float
    timeout_seconds: float = field(default=30.0)

    def is_expired(self) -> bool:
        """Vérifie si la session a expiré."""
        elapsed = time() - self.last_activity_at
        return elapsed > self.timeout_seconds

    def mark_activity(self) -> None:
        """Marque une activité pour redémarrer le timeout."""
        self.last_activity_at = time()


class SessionManager:
    """Gestionnaire de sessions utilisateur avec timeouts."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = max(0.01, timeout_seconds)
        self.sessions: dict[str, Session] = {}

    def start_session(self) -> Session:
        """Démarre une nouvelle session."""
        session_id = str(uuid4())
        now = time()
        session = Session(
            session_id=session_id,
            state=SessionState.ACTIVE,
            started_at=now,
            last_activity_at=now,
            timeout_seconds=self.timeout_seconds,
        )
        self.sessions[session_id] = session
        return session

    def is_session_active(self, session_id: str) -> bool:
        """Vérifie si une session est active (existe et n'a pas expiré)."""
        session = self.sessions.get(session_id)
        if session is None:
            return False

        if session.state == SessionState.CLOSED:
            return False

        if session.is_expired():
            session.state = SessionState.EXPIRED
            return False

        return True

    def resume_session(self, session_id: str) -> Session | None:
        """Réactive une session existante (si pas expirée).

        Returns:
            Session réactivée ou None si session inexistante ou expirée.
        """
        if not self.is_session_active(session_id):
            return None

        session = self.sessions[session_id]
        session.mark_activity()
        return session

    def record_activity(self, session_id: str) -> bool:
        """Enregistre une activité (redémarre le timeout).

        Returns:
            True si la session était active et l'activité a été enregistrée.
        """
        if not self.is_session_active(session_id):
            return False

        session = self.sessions[session_id]
        session.mark_activity()
        return True

    def close_session(self, session_id: str) -> bool:
        """Ferme explicitement une session.

        Returns:
            True si la session existait et a été fermée.
        """
        session = self.sessions.get(session_id)
        if session is None:
            return False

        session.state = SessionState.CLOSED
        return True

    def cleanup_expired_sessions(self) -> int:
        """Nettoie les sessions expirées. Returns le nombre supprimé."""
        expired_ids = [
            sid for sid, session in self.sessions.items() if session.is_expired()
        ]
        for sid in expired_ids:
            del self.sessions[sid]
        return len(expired_ids)
