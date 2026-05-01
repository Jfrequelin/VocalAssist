from __future__ import annotations

from uuid import uuid4

from src.assistant.orchestrator import handle_message
from src.assistant.session_manager import SessionManager
from src.assistant.system_messages import SystemMessages
from src.assistant.wake_word_handler import WakeWordHandler


def run_prototype() -> None:
    handler = WakeWordHandler(wake_word="nova")
    session_manager = SessionManager(timeout_seconds=120)  # 2 minutes inactivité

    print("=== Prototype assistant vocal (terminal) ===")
    print("Tapez vos commandes. Commencez par le mot cle 'nova'.")
    print("Exemple: nova quelle heure est-il")
    print("Pour quitter: nova stop")
    print("Pour l'aide: nova aide")

    current_session = None

    while True:
        raw = input("\nVous: ").strip()
        if not raw:
            continue

        result = handler.extract_command(raw)
        if not result.activated:
            print(f"Assistant: {SystemMessages.WAKE_WORD_MISSING}")
            continue

        # Activation détectée: démarrer ou reprendre une session
        if current_session is None or not session_manager.is_session_active(current_session.session_id):
            current_session = session_manager.start_session()
            print(f"[Session {current_session.session_id} demarree]")
        else:
            session_manager.record_activity(current_session.session_id)

        if result.is_help_requested:
            print(f"Assistant: {SystemMessages.format_help_message()}")
            session_manager.record_activity(current_session.session_id)
            continue

        message = result.command
        if not message:
            print(f"Assistant: {SystemMessages.COMMAND_EMPTY}")
            session_manager.record_activity(current_session.session_id)
            continue

        correlation_id = str(uuid4())
        reply = handle_message(message, use_leon_fallback=True, correlation_id=correlation_id)
        print(f"Assistant(trace): {SystemMessages.format_trace(reply.correlation_id, reply.source)}")
        if reply.source == "leon":
            print(f"Assistant: {SystemMessages.LEON_RESPONSE_SOURCE}")
        elif reply.source == "fallback-error":
            print(f"Assistant: {SystemMessages.LEON_UNAVAILABLE}")

        print(f"Assistant: {reply.answer}")

        # Enregistrer l'activité pour étendre le timeout
        session_manager.record_activity(current_session.session_id)

        if reply.intent == "exit":
            session_manager.close_session(current_session.session_id)
            print(f"[Session {current_session.session_id} fermee]")
            current_session = None
            break
