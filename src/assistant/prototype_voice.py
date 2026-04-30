from __future__ import annotations

import os
from time import perf_counter

from src.assistant.orchestrator import handle_message
from src.assistant.voice_pipeline import (
    FasterWhisperSpeechToText,
    MockSpeechToText,
    MockTextToSpeech,
    PiperTextToSpeech,
    SpeechToTextEngine,
    TextToSpeechEngine,
)

WAKE_WORD = "nova"


def _build_stt() -> SpeechToTextEngine:
    if os.getenv("ASSISTANT_VOICE_ENGINE", "mock").lower() != "real":
        return MockSpeechToText()

    model_size = os.getenv("ASSISTANT_STT_MODEL", "small")
    try:
        return FasterWhisperSpeechToText(model_size=model_size, language="fr")
    except RuntimeError as exc:
        print(f"Assistant: STT reel indisponible ({exc}), fallback mock")
        return MockSpeechToText()


def _build_tts() -> TextToSpeechEngine:
    if os.getenv("ASSISTANT_VOICE_ENGINE", "mock").lower() != "real":
        return MockTextToSpeech()

    model_path = os.getenv("PIPER_MODEL_PATH", "").strip()
    if not model_path:
        print("Assistant: PIPER_MODEL_PATH absent, fallback TTS mock")
        return MockTextToSpeech()

    try:
        return PiperTextToSpeech(model_path=model_path)
    except RuntimeError as exc:
        print(f"Assistant: TTS reel indisponible ({exc}), fallback mock")
        return MockTextToSpeech()


def run_prototype_voice() -> None:
    stt = _build_stt()
    tts = _build_tts()

    print("=== Prototype vocal (pipeline STT/TTS simule) ===")
    print("Entree attendue: texte representant l'audio capture")
    print("Mode reel: ASSISTANT_VOICE_ENGINE=real et entree possible via chemin fichier audio")
    print("Exemple: nova quelle heure est-il")
    print("Pour quitter: nova stop")

    while True:
        audio_payload = input("\nAudio(simule): ").strip()
        if not audio_payload:
            continue

        total_start = perf_counter()
        stt_start = perf_counter()
        transcription = stt.transcribe(audio_payload)
        stt_ms = (perf_counter() - stt_start) * 1000
        lowered = transcription.lower()

        if not lowered.startswith(WAKE_WORD):
            print("Assistant: mot cle absent, commande ignoree.")
            continue

        message = lowered[len(WAKE_WORD) :].strip()
        if not message:
            print("Assistant: commande vide apres le mot cle.")
            continue

        orchestrator_start = perf_counter()
        reply = handle_message(message, use_leon_fallback=True)
        orchestrator_ms = (perf_counter() - orchestrator_start) * 1000
        if reply.source == "leon":
            print("Assistant: reponse fournie par Leon")
        elif reply.source == "fallback-error":
            print("Assistant: Leon indisponible, fallback local impossible")

        tts_start = perf_counter()
        try:
            speech_output = tts.synthesize(reply.answer)
        except RuntimeError as exc:
            print(f"Assistant: TTS reel en erreur ({exc}), fallback texte")
            speech_output = reply.answer
        tts_ms = (perf_counter() - tts_start) * 1000

        total_ms = (perf_counter() - total_start) * 1000

        print(f"Assistant(TTS): {speech_output}")
        print(
            f"Assistant(metrics): stt={stt_ms:.1f}ms, orchestrateur={orchestrator_ms:.1f}ms, "
            f"tts={tts_ms:.1f}ms, total={total_ms:.1f}ms"
        )

        if reply.intent == "exit":
            break
