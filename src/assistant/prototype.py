from __future__ import annotations

from src.assistant.orchestrator import handle_message

WAKE_WORD = "nova"


def run_prototype() -> None:
    print("=== Prototype assistant vocal (terminal) ===")
    print("Tapez vos commandes. Commencez par le mot cle 'nova'.")
    print("Exemple: nova quelle heure est-il")
    print("Pour quitter: nova stop")
    print("Pour l'aide: nova aide")

    while True:
        raw = input("\nVous: ").strip()
        if not raw:
            continue

        lowered = raw.lower()
        if not lowered.startswith(WAKE_WORD):
            print("Assistant: mot cle absent, commande ignoree.")
            continue

        message = lowered[len(WAKE_WORD) :].strip()
        if not message:
            print("Assistant: commande vide apres le mot cle.")
            continue

        if message in {"aide", "help"}:
            print("Assistant: intents supportes -> heure, date, meteo, musique, lumiere, rappel, agenda, stop")
            print("Assistant: fallback Leon actif si intent inconnu.")
            continue

        reply = handle_message(message, use_leon_fallback=True)
        if reply.source == "leon":
            print("Assistant: reponse fournie par Leon")
        elif reply.source == "fallback-error":
            print("Assistant: Leon indisponible, fallback local impossible")

        print(f"Assistant: {reply.answer}")

        if reply.intent == "exit":
            break
