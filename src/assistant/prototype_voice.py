from __future__ import annotations

import os
from time import perf_counter
from uuid import uuid4

from src.assistant.orchestrator import handle_message
from src.assistant.session_manager import SessionManager
from src.assistant.system_messages import SystemMessages
from src.assistant.wake_word_handler import WakeWordHandler
from src.assistant.voice_pipeline import (
    FasterWhisperSpeechToText,
    MockSpeechToText,
    MockTextToSpeech,
    PiperTextToSpeech,
    SpeechToTextEngine,
    TextToSpeechEngine,
)


def _build_stt() -> SpeechToTextEngine:
    if os.getenv("ASSISTANT_VOICE_ENGINE", "mock").lower() != "real":
        return MockSpeechToText()

    model_size = os.getenv("ASSISTANT_STT_MODEL", "small")
    try:
        return FasterWhisperSpeechToText(model_size=model_size, language="fr")
    except RuntimeError as exc:
        print(f"Assistant: {SystemMessages.format_stt_error(exc)}")
        return MockSpeechToText()


def _build_tts() -> TextToSpeechEngine:
    if os.getenv("ASSISTANT_VOICE_ENGINE", "mock").lower() != "real":
        return MockTextToSpeech()

    model_path = os.getenv("PIPER_MODEL_PATH", "").strip()
    if not model_path:
        print(f"Assistant: {SystemMessages.TTS_PIPER_PATH_MISSING}")
        return MockTextToSpeech()

    try:
        return PiperTextToSpeech(model_path=model_path)
    except RuntimeError as exc:
        print(f"Assistant: {SystemMessages.TTS_ENGINE_FALLBACK}: {exc}")
        return MockTextToSpeech()


def run_prototype_voice() -> None:
    handler = WakeWordHandler(wake_word="nova")
    stt = _build_stt()
    tts = _build_tts()
    session_manager = SessionManager(timeout_seconds=60)  # 1 minute inactivité pour vocal

    print("=== Prototype vocal (pipeline STT/TTS simule) ===")
    print("Entree attendue: texte representant l'audio capture")
    print("Mode reel: ASSISTANT_VOICE_ENGINE=real et entree possible via chemin fichier audio")
    print("Exemple: nova quelle heure est-il")
    print("Pour quitter: nova stop")

    current_session = None

    while True:
        audio_payload = input("\nAudio(simule): ").strip()
        if not audio_payload:
            continue

        total_start = perf_counter()
        stt_start = perf_counter()
        transcription = stt.transcribe(audio_payload)
        stt_ms = (perf_counter() - stt_start) * 1000

        result = handler.extract_command(transcription)
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

        orchestrator_start = perf_counter()
        correlation_id = str(uuid4())
        reply = handle_message(message, use_leon_fallback=True, correlation_id=correlation_id)
        orchestrator_ms = (perf_counter() - orchestrator_start) * 1000
        print(f"Assistant(trace): {SystemMessages.format_trace(reply.correlation_id, reply.source)}")
        if reply.source == "leon":
            print(f"Assistant: {SystemMessages.LEON_RESPONSE_SOURCE}")
        elif reply.source == "fallback-error":
            print(f"Assistant: {SystemMessages.LEON_UNAVAILABLE}")

        tts_start = perf_counter()
        try:
            speech_output = tts.synthesize(reply.answer)
        except RuntimeError as exc:
            print(f"Assistant: {SystemMessages.format_tts_error(exc)}")
            speech_output = reply.answer
        tts_ms = (perf_counter() - tts_start) * 1000

        total_ms = (perf_counter() - total_start) * 1000

        print(f"Assistant(TTS): {speech_output}")
        print(
            f"Assistant(metrics): stt={stt_ms:.1f}ms, orchestrateur={orchestrator_ms:.1f}ms, "
            f"tts={tts_ms:.1f}ms, total={total_ms:.1f}ms"
        )

        # Enregistrer l'activité pour étendre le timeout
        session_manager.record_activity(current_session.session_id)

        if reply.intent == "exit":
            session_manager.close_session(current_session.session_id)
            print(f"[Session {current_session.session_id} fermee]")
            current_session = None
            break
