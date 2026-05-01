from __future__ import annotations

import os

from src.assistant.edge_audio import (
    build_edge_audio_payload,
    evaluate_edge_activation,
    send_edge_audio_payload,
)
from src.assistant.edge_device import EdgeDeviceController
from src.assistant.voice_pipeline import MockTextToSpeech


def _print_banner(base_url: str, wake_word: str) -> None:
    print("=== Prototype edge: capture -> envoi serveur ===")
    print(f"Backend: {base_url}/edge/audio")
    print("Entree attendue: texte simulant un flux micro brut")
    print(f"Activation locale: wake word '{wake_word}' + VAD minimal")
    print("Commandes: /status, /mute, /unmute, /button, quit")
    print("Commande 'quit' pour sortir")


def _handle_control_command(raw: str, controller: EdgeDeviceController) -> bool:
    command = raw.lower()
    if command == "/status":
        print(f"Edge(state): {controller.describe()}")
        return True
    if command == "/mute":
        controller.set_mute(True)
        print(f"Edge(state): {controller.describe()}")
        return True
    if command == "/unmute":
        controller.set_mute(False)
        print(f"Edge(state): {controller.describe()}")
        return True
    if command == "/button":
        controller.press_button()
        print("Edge: interaction coupee par bouton utilisateur")
        print(f"Edge(state): {controller.describe()}")
        return True
    return False


def _process_audio_segment(
    raw: str,
    wake_word: str,
    device_id: str,
    base_url: str,
    retry_attempts: int,
    retry_backoff_seconds: float,
    controller: EdgeDeviceController,
    tts: MockTextToSpeech,
) -> None:
    decision = evaluate_edge_activation(raw, wake_word=wake_word)
    if not decision.should_send:
        print(f"Edge: segment ignore ({decision.reason})")
        return

    controller.start_interaction()
    print(f"Edge(state): {controller.describe()}")
    payload = build_edge_audio_payload(decision.command.encode("utf-8"), device_id=device_id)
    controller.mark_sending()
    print(f"Edge(state): {controller.describe()}")
    response = send_edge_audio_payload(
        payload,
        base_url=base_url,
        retry_attempts=retry_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )

    if not response:
        controller.mark_error()
        print("Edge: envoi echoue ou reponse invalide du backend")
        print("Edge: mode degrade active (reconnexion automatique au prochain segment)")
        print(f"Edge(state): {controller.describe()}")
        return

    controller.mark_speaking()
    print(f"Edge(state): {controller.describe()}")
    answer = str(response.get("answer", "Payload accepte."))
    spoken = tts.synthesize(answer)
    if controller.state.muted:
        print("Edge(TTS): muet, restitution audio supprimee")
    else:
        print(f"Edge(TTS): {spoken}")

    controller.finish_interaction()
    print(f"Edge(state): {controller.describe()}")
    print(
        "Edge: payload accepte "
        f"(cid={response.get('correlation_id')}, bytes={response.get('received_bytes')}, "
        f"intent={response.get('intent')}, source={response.get('source')})"
    )


def run_prototype_edge() -> None:
    base_url = os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8081")
    device_id = os.getenv("EDGE_DEVICE_ID", "esp32-s3-dev")
    wake_word = os.getenv("EDGE_WAKE_WORD", "nova")
    retry_attempts = int(os.getenv("EDGE_SEND_RETRY_ATTEMPTS", "2"))
    retry_backoff_seconds = float(os.getenv("EDGE_SEND_RETRY_BACKOFF_SECONDS", "0.1"))
    controller = EdgeDeviceController()
    tts = MockTextToSpeech()

    _print_banner(base_url, wake_word)

    while True:
        raw = input("\nAudio brut(simule): ").strip()
        if not raw:
            continue
        if raw.lower() in {"quit", "exit", "stop"}:
            break
        if _handle_control_command(raw, controller):
            continue

        _process_audio_segment(
            raw,
            wake_word,
            device_id,
            base_url,
            retry_attempts,
            retry_backoff_seconds,
            controller,
            tts,
        )
