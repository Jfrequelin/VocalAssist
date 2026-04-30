from __future__ import annotations

from src.assistant.orchestrator import handle_message
from src.assistant.voice_pipeline import MockSpeechToText, MockTextToSpeech

WAKE_WORD = "nova"


def run_prototype_voice() -> None:
    stt = MockSpeechToText()
    tts = MockTextToSpeech()

    print("=== Prototype vocal (pipeline STT/TTS simule) ===")
    print("Entree attendue: texte representant l'audio capture")
    print("Exemple: nova quelle heure est-il")
    print("Pour quitter: nova stop")

    while True:
        audio_payload = input("\nAudio(simule): ").strip()
        if not audio_payload:
            continue

        transcription = stt.transcribe(audio_payload)
        lowered = transcription.lower()

        if not lowered.startswith(WAKE_WORD):
            print("Assistant: mot cle absent, commande ignoree.")
            continue

        message = lowered[len(WAKE_WORD) :].strip()
        if not message:
            print("Assistant: commande vide apres le mot cle.")
            continue

        reply = handle_message(message, use_leon_fallback=True)
        if reply.source == "leon":
            print("Assistant: reponse fournie par Leon")
        elif reply.source == "fallback-error":
            print("Assistant: Leon indisponible, fallback local impossible")

        speech_output = tts.synthesize(reply.answer)
        print(f"Assistant(TTS): {speech_output}")

        if reply.intent == "exit":
            break
