from __future__ import annotations

from uuid import uuid4

from src.assistant.orchestrator import handle_message
from src.assistant.wake_word_handler import WakeWordHandler


def run_prototype() -> None:
    handler = WakeWordHandler(wake_word="nova")
    print("=== Prototype assistant vocal (terminal) ===")
    print("Tapez vos commandes. Commencez par le mot cle 'nova'.")
    print("Exemple: nova quelle heure est-il")
    print("Pour quitter: nova stop")
    print("Pour l'aide: nova aide")

    while True:
        raw = input("\nVous: ").strip()
        if not raw:
            continue

        result = handler.extract_command(raw)
        if not result.activated:
            print("Assistant: mot cle absent, commande ignoree.")
            continue

        if result.is_help_requested:
            print("Assistant: intents supportes -> heure, date, meteo, musique, lumiere, rappel, agenda, stop")
            print("Assistant: fallback Leon actif si intent inconnu.")
            continue

        message = result.command
        if not message:
            print("Assistant: commande vide apres le mot cle.")
            continue

        correlation_id = str(uuid4())
        reply = handle_message(message, use_leon_fallback=True, correlation_id=correlation_id)
        print(f"Assistant(trace): cid={reply.correlation_id} source={reply.source}")
        if reply.source == "leon":
            print("Assistant: reponse fournie par Leon")
        elif reply.source == "fallback-error":
            print("Assistant: Leon indisponible, fallback local impossible")

        print(f"Assistant: {reply.answer}")

        if reply.intent == "exit":
            break
