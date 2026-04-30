from __future__ import annotations

import os

from src.assistant.edge_audio import build_edge_audio_payload, send_edge_audio_payload


def run_prototype_edge() -> None:
    base_url = os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8081")
    device_id = os.getenv("EDGE_DEVICE_ID", "esp32-s3-dev")

    print("=== Prototype edge: capture -> envoi serveur ===")
    print(f"Backend: {base_url}/edge/audio")
    print("Entree attendue: texte simulant un flux micro brut")
    print("Commande 'quit' pour sortir")

    while True:
        raw = input("\nAudio brut(simule): ").strip()
        if not raw:
            continue
        if raw.lower() in {"quit", "exit", "stop"}:
            break

        payload = build_edge_audio_payload(raw.encode("utf-8"), device_id=device_id)
        response = send_edge_audio_payload(payload, base_url=base_url)

        if not response:
            print("Edge: envoi echoue ou reponse invalide du backend")
            continue

        print(
            "Edge: payload accepte "
            f"(cid={response.get('correlation_id')}, bytes={response.get('received_bytes')})"
        )
